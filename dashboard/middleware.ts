// Public-deployment gate. When the Next server has PB_DEMO_BASIC="user:pass"
// set, every request from a non-local Host must carry that basic-auth
// credential (the browser prompts once per origin). localhost and the WSL LAN
// address stay open so the on-stage demo never hits a password prompt.
// With the variable unset the gate is disabled entirely.
//
// Runs on the Edge runtime: no Node crypto/Buffer — Web Crypto only.
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const LOCAL_HOSTS = [
  "localhost:3000",
  "127.0.0.1:3000",
  "172.28.99.44:3000",
];

/** Constant-time-ish compare via SHA-256 digests (equal length always). */
async function safeEqual(a: string, b: string): Promise<boolean> {
  const enc = new TextEncoder();
  const [ab, bb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b)),
  ]);
  const av = new Uint8Array(ab);
  const bv = new Uint8Array(bb);
  let diff = 0;
  for (let i = 0; i < av.length; i++) diff |= av[i] ^ bv[i];
  return diff === 0;
}

export async function middleware(req: NextRequest) {
  const cred = process.env.PB_DEMO_BASIC ?? "";
  const host = (req.headers.get("host") ?? "").toLowerCase();
  if (!cred || LOCAL_HOSTS.includes(host)) return NextResponse.next();

  const auth = req.headers.get("authorization") ?? "";
  if (auth.startsWith("Basic ")) {
    const decoded = atob(auth.slice(6));
    if (await safeEqual(decoded, cred)) return NextResponse.next();
  }
  return new NextResponse("401 Authorization required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="PromptBreaker Demo", charset="UTF-8"',
    },
  });
}

// Static assets skip the gate; the browser reuses the origin's cached
// credentials for them after the first challenge.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
