import Phaser from 'phaser'

// Same hull/thruster look as the original static mockup, now driven by
// server-authoritative state. No physics of its own — see design spec's
// non-goals (no client-side prediction).
const PALETTE = {
  ship: 0xf5ead8,
  shipBorder: 0x56633f,
  thruster: 0xf6a06b,
}

const SHIP_SIZE = 66

export default class RemoteShip extends Phaser.GameObjects.Container {
  constructor(scene, x, y) {
    super(scene, x, y)
    scene.add.existing(this)

    const half = SHIP_SIZE / 2

    const thruster = scene.add.graphics()
    thruster.fillStyle(PALETTE.thruster, 1)
    thruster.fillRoundedRect(-48, -5, 96, 10, 5)
    thruster.setPosition(38, -52)
    thruster.setRotation(Phaser.Math.DegToRad(-52))

    const hull = scene.add.graphics()
    hull.fillStyle(PALETTE.ship, 1)
    hull.fillRoundedRect(-half, -half, SHIP_SIZE, SHIP_SIZE, 10)
    hull.lineStyle(2, PALETTE.shipBorder, 1)
    hull.strokeRoundedRect(-half, -half, SHIP_SIZE, SHIP_SIZE, 10)
    hull.setRotation(Phaser.Math.DegToRad(45))

    // The thruster flame marks the ship's rear. The server applies thrust
    // force along local +x (rotation 0) — see GameSessionService's
    // session.py _apply_input — so rotate the whole art group here until
    // the point opposite the thruster (the nose) lines up with local +x.
    // That keeps "up" always visually matching the direction physics
    // actually pushes the ship.
    const art = scene.add.container(0, 0, [thruster, hull])
    const noseAngle = Math.atan2(-52, 38) + Math.PI
    art.setRotation(-noseAngle)

    this.add(art)
  }

  applyState({ x, y, rotation }) {
    this.setPosition(x, y)
    this.setRotation(rotation)
  }
}
