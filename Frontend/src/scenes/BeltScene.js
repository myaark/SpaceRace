import Phaser from 'phaser'

// Amber-phosphor palette, ported from the "Belt run HUD" design (variant 1a).
const PALETTE = {
  void: 0x231f1b,
  outerFence: 0xaebf92,
  outerFenceFill: 0x7a8a5e,
  innerFence: 0xf6a06b,
  planetFill: 0xe8c887,
  planetBorder: 0xc67139,
  asteroidFill: 0x17140f,
  asteroidBorder: 0x645c50,
  salvageRing: 0xaebf92,
  hostileBox: 0xf6a06b,
  ship: 0xf5ead8,
  shipBorder: 0x56633f,
  thruster: 0xf6a06b,
  tether: 0xc67139,
}

const WORLD_W = 1280
const WORLD_H = 720

// All three belt rings share one center, so only their upper-right arcs
// sweep through the viewport — the planet reads as a close, zoomed-in limb.
const BELT_CENTER = { x: -200, y: 1500 }
const OUTER_FENCE_R = 1760
const INNER_FENCE_R = 1420
const PLANET_R = 1300

const ASTEROIDS = [
  { x: 574, y: 262, r: 30, drift: true, period: 17000 },
  { x: 835, y: 500, r: 26, drift: false },
  { x: 981, y: 277, r: 44, drift: true, period: 23000 },
  { x: 490, y: 202, r: 36, drift: false },
  { x: 906, y: 182, r: 34, drift: true, period: 29000 },
  { x: 798, y: 223, r: 28, drift: false },
  { x: 804, y: 385, r: 48, drift: true, period: 19000 },
  { x: 1063, y: 363, r: 40, drift: false },
  { x: 966, y: 589, r: 32, drift: true, period: 21000 },
  { x: 1123, y: 673, r: 26, drift: false },
]

const SALVAGE = { x: 804, y: 385, r: 64 }
const HOSTILE = { x: 627, y: 177, w: 70, h: 70 }
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
    this.drawAsteroids()
    this.drawHostileMarker()
    this.drawPlayerShip()
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

  drawAsteroids() {
    for (const a of ASTEROIDS) {
      const g = this.add.graphics()
      g.fillStyle(PALETTE.asteroidFill, 1)
      g.fillCircle(0, 0, a.r)
      g.lineStyle(1, PALETTE.asteroidBorder, 1)
      g.strokeCircle(0, 0, a.r)
      g.setPosition(a.x, a.y)

      if (a.drift) {
        this.tweens.add({
          targets: g,
          x: { from: a.x, to: a.x - 12 },
          y: { from: a.y, to: a.y + 7 },
          duration: a.period / 2,
          ease: 'Sine.easeInOut',
          yoyo: true,
          repeat: -1,
        })
      }
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

  drawPlayerShip() {
    const half = SHIP.size / 2

    const thruster = this.add.graphics()
    thruster.fillStyle(PALETTE.thruster, 1)
    thruster.fillRoundedRect(-48, -5, 96, 10, 5)
    thruster.setPosition(SHIP.x + 38, SHIP.y - 52)
    thruster.setRotation(Phaser.Math.DegToRad(-52))

    const hull = this.add.graphics()
    hull.fillStyle(PALETTE.ship, 1)
    hull.fillRoundedRect(-half, -half, SHIP.size, SHIP.size, 10)
    hull.lineStyle(2, PALETTE.shipBorder, 1)
    hull.strokeRoundedRect(-half, -half, SHIP.size, SHIP.size, 10)
    hull.setPosition(SHIP.x, SHIP.y)
    hull.setRotation(Phaser.Math.DegToRad(45))
  }
}
