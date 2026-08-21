# Asteroid Belt Battleground — Game Plan

---

## 1. Game Overview

Asteroid Belt Battleground is a browser-based, real-time multiplayer space shooter. Players pilot spaceships inside the asteroid belt of a planet, competing to destroy asteroids and eliminate other players for points. The game follows a match-based structure similar to FPS arena shooters — players spawn, fight, die, cool down, and respawn — all within a confined asteroid belt arena.

---

## 2. How the Game Works

### The Arena
The playable area is the asteroid belt of a planet. Players are restricted to this belt — they cannot fly freely into open space. The belt acts as the natural boundary of the map, creating a contained, chaotic combat zone filled with floating asteroids.

### Players & Spaceships
Each player controls a single spaceship. Ships can move within the asteroid belt, fire weapons at other players, and destroy asteroids. Every player is represented persistently — they don't disappear when they die, they simply enter a cooldown/respawn phase.

### Scoring
- Destroying an asteroid → points
- Destroying another player's ship → points
- Points are tracked per match and contribute to a global leaderboard

### Death & Respawn
When a player's ship is destroyed, they enter a cooldown period. After the cooldown expires, they respawn at a spawn point within the asteroid belt — similar to how FPS games handle respawning. Spawn points are distributed across the belt to avoid spawn-killing.

### Match Structure
- Each match supports **2 to 10 players**
- Matches are self-contained sessions
- When a match ends, scores are submitted and players can queue for a new match
- The website can support **50–100 concurrent players** across multiple simultaneous matches

---

## 3. Tech Stack

### Frontend
| Layer | Technology |
|---|---|
| Game Engine | **Phaser.js** |
| Rendering | HTML5 Canvas / WebGL (handled by Phaser) |
| Language | JavaScript |
| Communication | WebSockets (native browser API) |

Phaser.js is the industry standard for browser-based 2D games. It handles rendering, input, sprite management, and basic physics, making it ideal for a space shooter with asteroid physics and projectile movement.

### Backend
| Layer | Technology |
|---|---|
| Language | **Python** |
| Web Framework | **FastAPI** |
| Real-time | **WebSockets** (via FastAPI) |
| Async Runtime | **asyncio** |
| Physics (server) | **pymunk** (2D physics library) |

### Data & Messaging
| Purpose | Technology |
|---|---|
| Session & queue state | **Redis** |
| Inter-service events | **Redis Pub/Sub** |
| Persistent data (players, scores) | **PostgreSQL** |
| Live leaderboard rankings | **Redis** (sorted sets) |

### Infrastructure
| Layer | Technology |
|---|---|
| Containerisation | **Docker** |
| Local development | **Docker Compose** |
| Reverse proxy / gateway | **Nginx** |
| Hosting | Single VPS (e.g. DigitalOcean, Hetzner) to start |

---

## 4. Architecture

### Microservices Overview

The backend is split into focused, independent services. Each service runs in its own Docker container and communicates over internal Docker networking.

```
                        [ Nginx — API Gateway ]
                                  |
          ┌───────────────────────┼───────────────────────┐
          ↓                       ↓                       ↓
   [Auth Service]        [Matchmaking Service]    [Player Service]
   FastAPI + PostgreSQL   FastAPI + Redis          FastAPI + PostgreSQL
                                  ↓
                       [Game Session Service]
                        Python + WebSockets
                         (one process per match)
                                  ↓
                              [Redis]
                         Pub/Sub + Game State
                                  ↓
                       [Leaderboard Service]
                        FastAPI + PostgreSQL + Redis
```

### Services Breakdown

**Auth Service**
Handles player registration, login, and JWT token issuance. Stateless by design — verifies identity, nothing more.

**Player Service**
Manages player profiles, persistent stats, and cosmetic data (ships/skins in the future). Backed by PostgreSQL.

**Matchmaking Service**
Accepts players into a queue and groups them into match rooms (2–10 players). Once a room is full or a time threshold is met, it signals the Game Session Service to start a match and returns the session connection details to the players.

**Game Session Service**
The core of the game. One Python process per active match. It runs the server-authoritative game loop, manages all player WebSocket connections for that match, processes player inputs, runs physics and collision detection, and broadcasts game state updates to all connected clients. When a match ends, it reports final scores to the Leaderboard Service and shuts down.

**Leaderboard Service**
Receives score events from completed matches. Maintains both per-match results and global rankings. Redis sorted sets power the live rankings; PostgreSQL stores historical data.

### Inter-Service Communication
- **REST over HTTP** — for non-time-critical calls (auth checks, profile fetches, leaderboard writes)
- **Redis Pub/Sub** — for internal events (match ready, player eliminated, session ended)
- **WebSockets** — exclusively between the game client (Phaser.js) and the Game Session Service

### Game Session — Process Model
Rather than Kubernetes pods, each match session is a **Python subprocess** spawned by the Matchmaking Service. This is simpler, runs on a single VPS, and is more than sufficient for the target scale. The process is given a room ID and an available port, accepts WebSocket connections from its assigned players, and exits cleanly when the match concludes.

---

## 5. Key Architecture Decisions

### Decision 1 — Server-Authoritative Game State
The server owns all game truth. Clients never decide what happened — they only send inputs (direction, fire, boost). The server processes those inputs, runs physics, resolves collisions, and broadcasts the resulting state back to all players.

This means:
- No client can cheat by falsifying their position or hit results
- All collision detection (ship vs ship, ship vs asteroid, bullet vs target) happens on the server
- The server runs a fixed-tick game loop (approximately 20 updates per second)

The trade-off is added complexity, particularly around making the game feel responsive despite network latency. This is managed through **basic client-side prediction** for movement — the client renders the local player's movement immediately while waiting for server confirmation, then corrects any mismatch when the authoritative state arrives. Full lag compensation (rewinding game state per shot) is deferred to a later stage.

### Decision 2 — No Kubernetes (for now)
Kubernetes adds significant operational overhead that is not justified at 50–100 concurrent players. Docker Compose on a single VPS is the starting infrastructure. The microservices architecture is designed to be Kubernetes-compatible when the time comes, but the immediate deployment strategy is simpler and faster to iterate on.

The scaling path is:
1. Docker Compose on a single VPS — handles initial launch
2. Docker Compose across 2 VPS nodes + Nginx load balancing — handles growth
3. Managed container platforms (AWS ECS or Google Cloud Run) — before considering K8s
4. Kubernetes — only if running many simultaneous game servers at high load

### Decision 3 — Redis as the Backbone
Redis serves multiple roles: matchmaking queues, inter-service pub/sub messaging, live leaderboard sorted sets, and ephemeral game session state. This keeps the system loosely coupled — services communicate through Redis events rather than direct HTTP calls for anything time-sensitive.

### Decision 4 — One Game Session Process Per Match
Each active match is an isolated Python process. This gives natural fault isolation — a crash in one match doesn't affect others. It also simplifies state management since each process only tracks its own 2–10 players, with no shared in-memory state between matches.

### Decision 5 — PostgreSQL for Persistence, Redis for Speed
Player profiles, match history, and leaderboard archives live in PostgreSQL for reliability. Anything that needs to be fast and temporary — active sessions, queues, live rankings — lives in Redis. The two are not in conflict; they serve different purposes.

---

## 6. Game Loop & State Management

### Server Game Loop (per match)
The game session runs a continuous async loop at a fixed tick rate. Each tick:
1. Collect all player inputs received since the last tick
2. Apply inputs to player ship state (position, velocity, orientation)
3. Spawn/update asteroids
4. Run physics simulation
5. Detect and resolve all collisions
6. Update scores and trigger death/respawn logic
7. Broadcast updated game state to all connected clients

### Client Rendering Loop
Phaser.js runs its own rendering loop independently of the server tick. The client:
1. Applies local prediction for the player's own ship movement
2. Interpolates other players' positions between received state updates for smooth rendering
3. Corrects its local state when a server update arrives that conflicts with the prediction

### State Broadcast
Full game state is sent every tick initially (positions, velocities, asteroid states, scores, player statuses). Delta compression — sending only what changed — is an optimisation for a later stage.

---

## 7. Player Movement & Boundary System

Movement is restricted to the asteroid belt. The belt is defined as an annular region (a ring) around the planet. The server enforces this boundary — any input that would move a player outside the belt is clamped server-side. The client visually represents the boundary so players understand their limits.

---

## 8. Respawn System

When a player is destroyed:
1. Server marks the player as dead and starts a cooldown timer
2. Client is notified and displays a respawn countdown
3. On cooldown expiry, the server selects a valid spawn point (distributed across the belt, away from active combat zones where possible)
4. Player is respawned at that point and re-enters the game loop

---

## 9. Scalability Considerations

The architecture is designed so that scaling does not require fundamental changes — only infrastructure additions:

- Additional VPS nodes can run more game session processes
- The stateless Auth and Player services scale horizontally behind Nginx
- Redis handles the shared state between nodes
- PostgreSQL can be promoted to a managed database service (e.g. RDS) without code changes
- The Matchmaking Service can be load-balanced since session state lives in Redis, not in the process

---

## 10. Deferred / Future Features

The following are intentional omissions from the initial build, to be added in later stages:

- Full lag compensation (server-side game state rewind per shot)
- Delta state compression for WebSocket broadcasts
- Ship cosmetics and inventory
- Spectator mode
- Persistent seasons / ranked mode
- Anti-cheat beyond server authority
- Kubernetes deployment
