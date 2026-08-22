// WebSocket wrapper for the game-session movement slice. Connects to a
// fixed dev room (matchmaking isn't wired up yet — see the design spec's
// non-goals), sends input on change, and delivers server state broadcasts.
export default class GameSocket {
  constructor(url) {
    this.url = url
    this.seq = 0
    this.stateHandlers = []
    this.initHandlers = []
    this.retriesLeft = 1
    this.ws = null
    this._connect()
  }

  _connect() {
    this.ws = new WebSocket(this.url)

    this.ws.addEventListener('message', (event) => {
      let message
      try {
        message = JSON.parse(event.data)
      } catch {
        return
      }
      if (message.type === 'state') {
        for (const handler of this.stateHandlers) handler(message)
      } else if (message.type === 'init') {
        for (const handler of this.initHandlers) handler(message)
      }
    })

    this.ws.addEventListener('close', () => {
      if (this.retriesLeft > 0) {
        this.retriesLeft -= 1
        this._connect()
      }
    })
  }

  onState(callback) {
    this.stateHandlers.push(callback)
  }

  onInit(callback) {
    this.initHandlers.push(callback)
  }

  sendInput({ thrust, turn }) {
    if (this.ws.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify({ type: 'input', seq: this.seq++, thrust, turn }))
  }
}
