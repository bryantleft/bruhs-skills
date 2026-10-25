# quill-web

The Quill web app's settings page (profile, workspace, notifications, API key). Vite +
React; no backend yet, so saving only validates and shows a message. Sample data and
helpers live in `src/settings.ts`.

```sh
npm install
npm run dev        # http://localhost:5173
npm test           # vitest
npm run typecheck
npm run build      # then `npm run preview` to serve dist/
```
