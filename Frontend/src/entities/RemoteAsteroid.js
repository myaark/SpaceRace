import Phaser from 'phaser'

// Same asteroid look as the original static mockup, now driven by
// server-authoritative state. No local motion logic — see design spec's
// non-goals (no client-side prediction).
const PALETTE = {
  asteroidFill: 0x17140f,
  asteroidBorder: 0x645c50,
}

export default class RemoteAsteroid extends Phaser.GameObjects.Container {
  constructor(scene, x, y, r) {
    super(scene, x, y)
    scene.add.existing(this)

    const g = scene.add.graphics()
    g.fillStyle(PALETTE.asteroidFill, 1)
    g.fillCircle(0, 0, r)
    g.lineStyle(1, PALETTE.asteroidBorder, 1)
    g.strokeCircle(0, 0, r)

    this.add(g)
  }

  applyState({ x, y }) {
    this.setPosition(x, y)
  }
}
