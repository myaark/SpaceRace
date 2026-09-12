import Phaser from 'phaser'

// Ship art now comes from the image assets under public/assests, one of
// three hulls picked per ship id. No physics of its own — see design
// spec's non-goals (no client-side prediction).
export const SHIP_TEXTURES = ['ship-spaceship', 'ship-interceptor', 'ship-scout']

const SHIP_SIZE = 66

function pickTexture(id) {
  let hash = 0
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0
  }
  return SHIP_TEXTURES[Math.abs(hash) % SHIP_TEXTURES.length]
}

export default class RemoteShip extends Phaser.GameObjects.Container {
  constructor(scene, x, y, id) {
    super(scene, x, y)
    scene.add.existing(this)

    const art = scene.add.image(0, 0, pickTexture(id))
    art.setDisplaySize(SHIP_SIZE, SHIP_SIZE)

    // The art is drawn nose-up. The server applies thrust force along
    // local +x (rotation 0) — see GameSessionService's session.py
    // _apply_input — and rotating a nose-up sprite by +90 degrees points
    // its nose along +x. That keeps "up" in the art always matching the
    // direction physics actually pushes the ship.
    art.setRotation(Phaser.Math.DegToRad(90))

    this.add(art)
  }

  applyState({ x, y, rotation }) {
    this.setPosition(x, y)
    this.setRotation(rotation)
  }
}
