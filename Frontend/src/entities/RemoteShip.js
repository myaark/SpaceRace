import Phaser from 'phaser'

// Ship art now comes from the image assets under public/assests, one of
// three hulls picked per ship id. No physics of its own — see design
// spec's non-goals (no client-side prediction).
export const SHIP_TEXTURES = ['ship-spaceship', 'ship-interceptor', 'ship-scout']

const SHIP_SIZE = 66
const HP_BAR_WIDTH = 40
const HP_BAR_HEIGHT = 4
const HP_BAR_OFFSET_Y = -(SHIP_SIZE / 2 + 10)

const PALETTE = {
  hpFill: 0xaebf92,
  hpEmpty: 0x4a4038,
}

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

    this.art = scene.add.image(0, 0, pickTexture(id))
    this.art.setDisplaySize(SHIP_SIZE, SHIP_SIZE)

    // The art is drawn nose-up. The server applies thrust force along
    // local +x (rotation 0) — see GameSessionService's session.py
    // _apply_input — and rotating a nose-up sprite by +90 degrees points
    // its nose along +x. That keeps "up" in the art always matching the
    // direction physics actually pushes the ship.
    this.art.setRotation(Phaser.Math.DegToRad(90))
    this.add(this.art)

    // HP bar rotates with the ship container — no independent screen-space
    // UI layer exists yet in this scene, so this keeps it simple.
    this.hpBar = scene.add.graphics()
    this.add(this.hpBar)
    this.drawHpBar(1)
  }

  drawHpBar(ratio) {
    this.hpBar.clear()
    this.hpBar.fillStyle(PALETTE.hpEmpty, 1)
    this.hpBar.fillRect(-HP_BAR_WIDTH / 2, HP_BAR_OFFSET_Y, HP_BAR_WIDTH, HP_BAR_HEIGHT)
    this.hpBar.fillStyle(PALETTE.hpFill, 1)
    this.hpBar.fillRect(-HP_BAR_WIDTH / 2, HP_BAR_OFFSET_Y, HP_BAR_WIDTH * ratio, HP_BAR_HEIGHT)
  }

  applyState({ x, y, rotation, hp, max_hp, alive }) {
    this.setPosition(x, y)
    this.setRotation(rotation)
    this.drawHpBar(Phaser.Math.Clamp(hp / max_hp, 0, 1))
    // A dead ship is never removed server-side (it stays in self.ships,
    // inert) — mirror that here: dim and gray it out rather than
    // destroying the sprite, so it keeps reading as "dead but present".
    this.setAlpha(alive ? 1 : 0.35)
    this.art.setTint(alive ? 0xffffff : 0x808080)
  }
}
