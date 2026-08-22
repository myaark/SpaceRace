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
const GAME_SESSION_WS_URL = 'ws://localhost:8000/ws/dev-room'

// Positions are placeholders shown before the first server state broadcast
// arrives — same role the SHIP constant plays for the ship. Radius is a
// frontend-only constant (never sent by the server, keyed by id). Must
// match Backend/GameSessionService/app/entities.py's ASTEROID_DEFS.
const ASTEROIDS = [
  { id: 'ast-1', x: 574, y: 262, r: 30 },
  { id: 'ast-2', x: 835, y: 500, r: 26 },
  { id: 'ast-3', x: 981, y: 277, r: 44 },
  { id: 'ast-4', x: 490, y: 202, r: 36 },
  { id: 'ast-5', x: 906, y: 182, r: 34 },
  { id: 'ast-6', x: 798, y: 223, r: 28 },
  { id: 'ast-7', x: 804, y: 385, r: 48 },
  { id: 'ast-8', x: 1063, y: 363, r: 40 },
  { id: 'ast-9', x: 966, y: 589, r: 32 },
  { id: 'ast-10', x: 1123, y: 673, r: 26 },
]

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

  create() {
    this.cameras.main.setBackgroundColor(PALETTE.void)

    this.drawBeltRings()
    this.drawTether()
    this.drawSalvageMarker()
    this.drawHostileMarker()

    this.remoteAsteroids = new Map(
      ASTEROIDS.map((a) => [a.id, new RemoteAsteroid(this, a.x, a.y, a.r)]),
    )

    this.remoteShip = new RemoteShip(this, SHIP.x, SHIP.y)
    this.gameSocket = new GameSocket(GAME_SESSION_WS_URL)
    this.gameSocket.onState((msg) => {
      this.remoteShip.applyState(msg.ship)
      for (const asteroidState of msg.asteroids) {
        this.remoteAsteroids.get(asteroidState.id)?.applyState(asteroidState)
      }
    })

    this.lastSentInput = { thrust: 0, turn: 0 }
    this.cursors = this.input.keyboard.createCursorKeys()
    this.wasdKeys = this.input.keyboard.addKeys('W,A,S,D')

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
    this.cameras.main.startFollow(this.remoteShip, true, 0.08, 0.08)
  }

  update() {
    const thrust = this.readThrust()
    const turn = this.readTurn()

    if (thrust !== this.lastSentInput.thrust || turn !== this.lastSentInput.turn) {
      this.lastSentInput = { thrust, turn }
      this.gameSocket.sendInput({ thrust, turn })
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
