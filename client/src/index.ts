import { serve } from "bun";
import index from "./index.html";

const server = serve({
  routes: {
    "/ralph-logo.png": new Response(Bun.file(new URL("./assets/ralph-logo.png", import.meta.url))),
    "/*": index,
  },

  development: process.env.NODE_ENV !== "production" && {
    hmr: true,
    console: true,
  },
});

console.log(`Server running at ${server.url}`);
