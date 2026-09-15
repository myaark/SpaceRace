import Phaser from 'phaser'

// Bullets are a Graphics primitive, same approach as RemoteAsteroid — no
// new image asset, no client-side prediction. Position/rotation mirror
// the server's per-tick BulletState exactly; the server owns all bullet
// physics (spawn, travel, expiry, collision).
const PALETTE = {
  bulletFill: 0xf6a06b,
}

const BULLET_LENGTH = 10
const BULLET_WIDTH = 2

export default class RemoteBullet extends Phaser.GameObjects.Container {
  constructor(scene, x, y, rotation) {
    super(scene, x, y)
    scene.add.existing(this)

    const g = scene.add.graphics()
    g.fillStyle(PALETTE.bulletFill, 1)
    g.fillRect(-BULLET_LENGTH / 2, -BULLET_WIDTH / 2, BULLET_LENGTH, BULLET_WIDTH)
    this.add(g)

    this.setRotation(rotation)
  }

  applyState({ x, y, rotation }) {
    this.setPosition(x, y)
    this.setRotation(rotation)
  }
}
