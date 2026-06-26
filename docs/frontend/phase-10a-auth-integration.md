# Phase 10A: Frontend Auth Integration

Phase 10A connects the Next.js frontend to the real FastAPI auth API.

## Backend Endpoints

The frontend uses:

- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/logout`

Browser requests go through Next rewrites:

- `/api/auth/login` -> FastAPI `/auth/login`
- `/api/auth/me` -> FastAPI `/auth/me`
- `/api/auth/logout` -> FastAPI `/auth/logout`

Set `BACKEND_URL` for the frontend server when FastAPI is not running at
`http://localhost:8000`.

## Token Storage

For the local demo, the opaque bearer token is stored in `localStorage` under:

- `vinuni-copilot-access-token`

A cached safe user object is also stored for smoother first paint, but the app
still calls `/auth/me` on load whenever a token exists. If `/auth/me` returns
`401`, the frontend clears the token and user state.

## Auth Provider

`AuthProvider` exposes:

- `user`
- `token`
- `isAuthenticated`
- `isLoading`
- `hydrated`
- `login(email, password)`
- `logout()`
- `hasRole(role)`

The UI keeps its existing compact role shape:

- Backend `student` -> frontend `student`
- Backend `global_admin`, `institute_admin`, or `staff` -> frontend `admin`

Protected student routes require the backend `student` role. Protected admin
routes require one of `global_admin`, `institute_admin`, or `staff`.

## Demo Accounts

The login screen shows demo backend accounts and uses the real login endpoint:

- `student.cs.demo@vinuni.edu.vn`
- `student.business.demo@vinuni.edu.vn`
- `student.health.demo@vinuni.edu.vn`
- `student.liberal.demo@vinuni.edu.vn`
- `admin.cecs.demo@vinuni.edu.vn`
- `admin.global.demo@vinuni.edu.vn`

Demo password:

- `Demo@123456`

## Known Limitations

- VinUni SSO is not wired in this phase.
- Student profile, ticket, notification, conversation-list, and chat-history UI
  data are still integrated in later phases.
- Existing chat calls now attach the bearer token when available so backend chat
  persistence can work, but no chat-history frontend UI is added in Phase 10A.
