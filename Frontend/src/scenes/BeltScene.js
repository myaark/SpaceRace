import Phaser from 'phaser'
import GameSocket from '../net/GameSocket.js'
import RemoteShip from '../entities/RemoteShip.js'
import RemoteAsteroid from '../entities/RemoteAsteroid.js'

// Amber-phosphor palette, ported from the "Belt run HUD" design (variant 1a).
const PALETTE = {
  void: 0x231f1b,
  outerFence: 0xaebf92,
  outerFenceFill: 0x7a8a5e,
  innerFence: 0xf6a06b,
  planetFill: 0xe8c887,
  planetBorder: 0xc67139,
  salvageRing: 0xaebf92,
  hostileBox: 0xf6a06b,
  tether: 0xc67139,
}

// All three belt rings share one center, so only their upper-right arcs
// sweep through the viewport — the planet reads as a close, zoomed-in limb.
//
// Must match Backend/GameSessionService/app/session.py's BELT_CENTER /
// OUTER_FENCE_R / INNER_FENCE_R — there is no shared-schema mechanism
// enforcing this, so keep the two in sync by hand.
const BELT_CENTER = { x: -200, y: 1500 }
const OUTER_FENCE_R = 1760
const INNER_FENCE_R = 1420
const PLANET_R = 1300

// Fixed dev room — matchmaking isn't wired up yet (see design spec non-goals).
const GAME_SESSION_WS_BASE_URL = 'ws://localhost:8000/ws/dev-room'

// Backend requires player_id to match ^[A-Za-z0-9_-]{1,32}$ — see
// GameSessionService's controllers/game_session.py PLAYER_ID_PATTERN.
function generatePlayerId() {
  return `player-${Math.random().toString(36).slice(2, 10)}`
}

const SALVAGE = { x: 804, y: 385, r: 64 }
const HOSTILE = { x: 627, y: 177, w: 70, h: 70 }
// Must match Backend/GameSessionService's BELT_CENTER + SPAWN_OFFSET — the
// server's first state broadcast places the ship here, so any mismatch
// makes it appear to teleport away from this placeholder position.
const SHIP = { x: 724, y: 318, size: 66 }
const TETHER_END = { x: 601, y: 476 }

export default class BeltScene extends Phaser.Scene {
  constructor() {
    super('BeltScene')
  }

  preload() {
    this.load.image('ship-spaceship', '/assests/spaceship.png')
    this.load.image('ship-interceptor', '/assests/interceptor-ship.png')
    this.load.image('ship-scout', '/assests/scout-ship.png')
  }

  create() {
    this.cameras.main.setBackgroundColor(PALETTE.void)

    this.drawBeltRings()
    this.drawTether()
    this.drawSalvageMarker()
    this.drawHostileMarker()

    // Asteroid layout (position + radius) is server-generated, not a
    // hardcoded local constant — populated once the "init" message arrives.
    this.remoteAsteroids = new Map()

    // Ships are keyed by the player_id the server assigned them (see
    // ShipState.id) — a room can hold more than one independently
    // controlled ship, so this is a Map like remoteAsteroids, not a
    // single instance.
    this.remoteShips = new Map()
    this.playerId = generatePlayerId()
    // Placeholder art shown before our own ship first appears in a state
    // broadcast; the camera follows this until our ship id shows up.
    this.placeholderShip = new RemoteShip(this, SHIP.x, SHIP.y, this.playerId)

    this.gameSocket = new GameSocket(`${GAME_SESSION_WS_BASE_URL}?player_id=${this.playerId}`)
    this.gameSocket.onInit((msg) => {
      for (const a of msg.asteroids) {
        this.remoteAsteroids.set(a.id, new RemoteAsteroid(this, a.x, a.y, a.r))
      }
    })
    this.gameSocket.onState((msg) => {
      const seen = new Set()
      for (const shipState of msg.ships) {
        seen.add(shipState.id)
        let ship = this.remoteShips.get(shipState.id)
        if (!ship) {
          ship = new RemoteShip(this, shipState.x, shipState.y, shipState.id)
          this.remoteShips.set(shipState.id, ship)
          if (shipState.id === this.playerId) {
            this.placeholderShip.destroy()
            this.cameras.main.startFollow(ship, true, 0.08, 0.08)
          }
        }
        ship.applyState(shipState)
      }
      for (const [id, ship] of this.remoteShips) {
        if (!seen.has(id)) {
          ship.destroy()
          this.remoteShips.delete(id)
        }
      }
      for (const asteroidState of msg.asteroids) {
        this.remoteAsteroids.get(asteroidState.id)?.applyState(asteroidState)
      }
    })

    this.lastSentInput = { thrust: 0, turn: 0, fire: false }
    this.cursors = this.input.keyboard.createCursorKeys()
    this.wasdKeys = this.input.keyboard.addKeys('W,A,S,D')

    // Left-click-to-fire. No fire-rate limiting on the client — the
    // backend has none either (see combat-mechanics plan §"Out of scope");
    // holding the button sends fire:true once (on the down-transition) and
    // the server spawns one bullet per tick for as long as it stays true.
    this.fireHeld = false
    this.input.on('pointerdown', () => {
      this.fireHeld = true
    })
    this.input.on('pointerup', () => {
      this.fireHeld = false
    })

    this.setupCamera()
  }

  setupCamera() {
    // Bounds cover the full belt ring so the camera can follow the ship
    // anywhere it's physically allowed to go (see session.py's
    // _clamp_to_belt, which clamps radially only — the ship can traverse
    // the whole ring, not just this arc).
    this.cameras.main.setBounds(
      BELT_CENTER.x - OUTER_FENCE_R,
      BELT_CENTER.y - OUTER_FENCE_R,
      OUTER_FENCE_R * 2,
      OUTER_FENCE_R * 2,
    )
    this.cameras.main.startFollow(this.placeholderShip, true, 0.08, 0.08)
  }

  update() {
    const thrust = this.readThrust()
    const turn = this.readTurn()
    const fire = this.fireHeld

    if (
      thrust !== this.lastSentInput.thrust ||
      turn !== this.lastSentInput.turn ||
      fire !== this.lastSentInput.fire
    ) {
      this.lastSentInput = { thrust, turn, fire }
      this.gameSocket.sendInput({ thrust, turn, fire })
    }
  }

  readThrust() {
    if (this.cursors.up.isDown || this.wasdKeys.W.isDown) return 1
    if (this.cursors.down.isDown || this.wasdKeys.S.isDown) return -1
    return 0
  }

  readTurn() {
    if (this.cursors.left.isDown || this.wasdKeys.A.isDown) return -1
    if (this.cursors.right.isDown || this.wasdKeys.D.isDown) return 1
    return 0
  }

  drawBeltRings() {
    const g = this.add.graphics()

    g.fillStyle(PALETTE.outerFenceFill, 0.1)
    g.fillCircle(BELT_CENTER.x, BELT_CENTER.y, OUTER_FENCE_R)
    this.strokeDashedCircle(g, BELT_CENTER.x, BELT_CENTER.y, OUTER_FENCE_R, PALETTE.outerFence, 2)

    g.fillStyle(PALETTE.void, 1)
    g.fillCircle(BELT_CENTER.x, BELT_CENTER.y, INNER_FENCE_R)
    this.strokeDashedCircle(g, BELT_CENTER.x, BELT_CENTER.y, INNER_FENCE_R, PALETTE.innerFence, 2)

    g.fillStyle(PALETTE.planetFill, 1)
    g.fillCircle(BELT_CENTER.x, BELT_CENTER.y, PLANET_R)
    g.lineStyle(3, PALETTE.planetBorder, 1)
    g.strokeCircle(BELT_CENTER.x, BELT_CENTER.y, PLANET_R)

    this.add
      .text(74, 296, 'KETH', {
        fontFamily: 'Georgia, serif',
        fontSize: '40px',
        color: '#8c491a',
      })
      .setRotation(Phaser.Math.DegToRad(26))
      .setOrigin(0, 0)

    this.add
      .text(80, 350, 'GRAVITY WELL · NO ENTRY', {
        fontFamily: 'sans-serif',
        fontSize: '10px',
        color: '#8c491a',
        letterSpacing: 2,
      })
      .setRotation(Phaser.Math.DegToRad(26))
      .setOrigin(0, 0)
  }

  strokeDashedCircle(graphics, cx, cy, radius, color, width, dash = 10, gap = 10) {
    graphics.lineStyle(width, color, 1)
    const circumference = 2 * Math.PI * radius
    const segments = Math.max(8, Math.floor(circumference / (dash + gap)))
    const step = (Math.PI * 2) / segments
    for (let i = 0; i < segments; i++) {
      const a0 = i * step
      const a1 = a0 + step * (dash / (dash + gap))
      graphics.beginPath()
      graphics.arc(cx, cy, radius, a0, a1, false)
      graphics.strokePath()
    }
  }

  drawSalvageMarker() {
    const g = this.add.graphics()
    this.strokeDashedCircle(g, SALVAGE.x, SALVAGE.y, SALVAGE.r, PALETTE.salvageRing, 1, 6, 5)

    this.add
      .text(SALVAGE.x + 76, SALVAGE.y - 33, 'SALVAGE · Fe-Ni', {
        fontFamily: 'sans-serif',
        fontSize: '10px',
        color: '#aebf92',
        letterSpacing: 2,
      })
      .setOrigin(0, 0)

    this.add
      .text(SALVAGE.x + 76, SALVAGE.y - 18, '1.2 km · tow rated', {
        fontFamily: 'sans-serif',
        fontSize: '10px',
        color: 'rgba(246,234,216,0.5)',
      })
      .setOrigin(0, 0)
  }

  drawHostileMarker() {
    const g = this.add.graphics()
    g.lineStyle(2, PALETTE.hostileBox, 1)
    g.strokeRect(HOSTILE.x - HOSTILE.w / 2, HOSTILE.y - HOSTILE.h / 2, HOSTILE.w, HOSTILE.h)

    const label = this.add
      .text(HOSTILE.x - HOSTILE.w / 2, HOSTILE.y - HOSTILE.h / 2 - 20, 'HOSTILE · SKIFF ×2', {
        fontFamily: 'sans-serif',
        fontSize: '10px',
        color: '#f6a06b',
        letterSpacing: 2,
      })
      .setOrigin(0, 0)

    this.tweens.add({
      targets: [g, label],
      alpha: { from: 1, to: 0.4 },
      duration: 800,
      yoyo: true,
      repeat: -1,
    })
  }

  drawTether() {
    const g = this.add.graphics()
    g.lineStyle(2, PALETTE.tether, 1)
    this.drawDashedLine(g, SHIP.x, SHIP.y, TETHER_END.x, TETHER_END.y, 7, 8)
  }

  drawDashedLine(graphics, x0, y0, x1, y1, dash, gap) {
    const dx = x1 - x0
    const dy = y1 - y0
    const length = Math.hypot(dx, dy)
    const segments = Math.floor(length / (dash + gap))
    const ux = dx / length
    const uy = dy / length
    for (let i = 0; i < segments; i++) {
      const start = i * (dash + gap)
      const end = start + dash
      graphics.beginPath()
      graphics.moveTo(x0 + ux * start, y0 + uy * start)
      graphics.lineTo(x0 + ux * end, y0 + uy * end)
      graphics.strokePath()
    }
  }
}
