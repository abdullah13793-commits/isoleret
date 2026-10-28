"""Deterministic media for the repository and the landing page: 3D orbit loops rendered frame by frame (no screen recording),
a guided tour with eased crossfades and captions, a README GIF, cover and social images, and screenshots.

python src/make_media.py gennemfoert|isoleret
"""
import functools
import http.server
import json
import math
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = ROOT / "renders" / "media"
FPS, W, H = 30, 1600, 900
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_B, FONT = r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\segoeui.ttf"

ORBIT_JS = """([a, zoom, lift]) => { const T = G.three, cam = T.camera || T.cam, ctl = T.controls || T.ctl;
  if (!window._orb) { const b = new THREE.Box3().setFromObject(T.model); const c = b.getCenter(new THREE.Vector3());
    window._orb = {c, off: cam.position.clone().sub(c)}; }
  const o = window._orb, off = o.off.clone().multiplyScalar(zoom); const ca = Math.cos(a), sa = Math.sin(a);
  cam.position.set(o.c.x + off.x * ca - off.z * sa, o.c.y + off.y + lift, o.c.z + off.x * sa + off.z * ca); ctl.target.copy(o.c); G.render(); }"""


def ease(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def orbit(pg, folder, seconds, amp, zoom0=1.0, zoom1=0.86, clip=None, sway=True):
    folder.mkdir(parents=True, exist_ok=True)
    pg.evaluate("window._orb = null; G.frozen = true")
    n = int(seconds * FPS)
    for i in range(n):
        t = i / n
        a = amp * math.sin(2 * math.pi * t) if sway else amp * t
        z = zoom0 + (zoom1 - zoom0) * (0.5 - 0.5 * math.cos(2 * math.pi * t))
        pg.evaluate(ORBIT_JS, [a, z, 0.0])
        pg.screenshot(path=str(folder / f"f{i:04d}.png"), clip=clip)
    return sorted(folder.glob("f*.png"))


def caption(img, title, sub, alpha, accent):
    if alpha <= 0:
        return img
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    ft, fs = ImageFont.truetype(FONT_B, 34), ImageFont.truetype(FONT, 22)
    tw = max(d.textlength(title, font=ft), d.textlength(sub, font=fs))
    x, y, w, h = 48, img.size[1] - 150, int(tw) + 64, 108
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=(10, 12, 16, int(205 * alpha)))
    d.rounded_rectangle([x, y, x + 6, y + h], 3, fill=accent + (int(255 * alpha),))
    d.text((x + 32, y + 16), title, font=ft, fill=(255, 255, 255, int(255 * alpha)))
    d.text((x + 32, y + 62), sub, font=fs, fill=(205, 212, 222, int(255 * alpha)))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def frames_still(path, seconds, mode="kenburns"):
    """Yield W x H frames from a still: slow eased zoom (kenburns) or an eased vertical pan for tall screenshots."""
    im = Image.open(path).convert("RGB")
    n = int(seconds * FPS)
    if im.width != W:
        im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
    for i in range(n):
        t = ease(i / max(1, n - 1))
        if mode == "scroll" and im.height > H:
            y = int((im.height - H) * t)
            yield im.crop((0, y, W, y + H))
        else:
            s = 1.0 + 0.055 * t
            cw, ch = int(W / s), int(H / s)
            base = im if im.height >= H else Image.new("RGB", (W, H), (12, 14, 18))
            if im.height < H:
                base.paste(im, (0, (H - im.height) // 2))
            x0 = int((W - cw) * (0.5 + 0.12 * (t - 0.5))); y0 = int((min(base.height, H) - ch) * 0.35)
            yield base.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS)


def frames_seq(paths):
    for p in paths:
        yield Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS) if Image.open(p).size != (W, H) else Image.open(p).convert("RGB")


def compose(scenes, out_mp4, accent, xfade=0.7):
    """scenes: [(frame_list, title, sub)]. Crossfade between scenes with an eased blend; captions fade in and out."""
    proc = subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                             "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)],
                            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    k = int(xfade * FPS)
    tail = None
    for si, (frames, title, sub) in enumerate(scenes):
        frames = list(frames)
        n = len(frames)
        for i, fr in enumerate(frames):
            a_in = min(1.0, i / (0.5 * FPS)) if si else min(1.0, i / (0.3 * FPS))
            a_out = min(1.0, (n - 1 - i) / (0.5 * FPS))
            fr = caption(fr, title, sub, ease(max(0.0, min(a_in, a_out))), accent)
            if tail is not None and i < k:
                # dip through the page background: outgoing fades and shrinks slightly, incoming settles in from 1.02
                t = (i + 1) / (k + 1)
                dark = Image.new("RGB", (W, H), (11, 13, 17))
                if t < 0.5:
                    a = ease(t * 2)
                    o = tail[i].resize((int(W * (1 - 0.02 * a)), int(H * (1 - 0.02 * a))), Image.LANCZOS)
                    base = dark.copy(); base.paste(o, ((W - o.width) // 2, (H - o.height) // 2))
                    fr = Image.blend(base, dark, a)
                else:
                    a = ease((t - 0.5) * 2)
                    s = 1.02 - 0.02 * a
                    zi = fr.resize((int(W * s), int(H * s)), Image.LANCZOS).crop((int(W * (s - 1) / 2), int(H * (s - 1) / 2), int(W * (s - 1) / 2) + W, int(H * (s - 1) / 2) + H))
                    fr = Image.blend(dark, zi, a)
            if si + 1 < len(scenes) and i >= n - k:
                if i == n - k:
                    tail = []
                tail.append(fr)
                continue
            proc.stdin.write(np.asarray(fr, dtype=np.uint8).tobytes())
        if si + 1 == len(scenes):
            tail = None
    proc.stdin.close()
    proc.wait()


def to_mp4(paths, out, crop=None):
    with tempfile.TemporaryDirectory() as td:
        for i, p in enumerate(paths):
            shutil.copy(p, Path(td) / f"f{i:04d}.png")
        subprocess.run([FFMPEG, "-y", "-framerate", str(FPS), "-i", str(Path(td) / "f%04d.png"), "-c:v", "libx264", "-preset", "slow", "-crf", "21",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], check=True, stderr=subprocess.DEVNULL)


def to_gif(mp4, out, width=760, fps=20):
    pal = out.with_suffix(".pal.png")
    subprocess.run([FFMPEG, "-y", "-i", str(mp4), "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen=max_colors=128:stats_mode=diff", str(pal)],
                   check=True, stderr=subprocess.DEVNULL)
    subprocess.run([FFMPEG, "-y", "-i", str(mp4), "-i", str(pal), "-lavfi", f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle",
                    str(out)], check=True, stderr=subprocess.DEVNULL)
    pal.unlink()


def cover(pg, base, hero, title, tagline, chips, accent_css, out, w, h):
    html = f"""<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800&display=swap" rel="stylesheet">
    <style>body{{margin:0;width:{w}px;height:{h}px;overflow:hidden;background:#0b0d11;font-family:Inter,sans-serif;color:#eef1f5;position:relative}}
    .g{{position:absolute;inset:0;background-image:linear-gradient(#1a1f28 1px,transparent 1px),linear-gradient(90deg,#1a1f28 1px,transparent 1px);background-size:44px 44px;mask-image:radial-gradient(ellipse at 70% 40%,#000 25%,transparent 75%)}}
    .glow{{position:absolute;width:{int(w*.7)}px;height:{int(w*.7)}px;right:-{int(w*.15)}px;top:-{int(w*.2)}px;background:radial-gradient(circle,{accent_css}33,transparent 60%)}}
    .l{{position:absolute;left:{int(w*.055)}px;top:{int(h*.16)}px;width:{int(w*.42)}px}}
    .b{{display:flex;align-items:center;gap:12px;font-weight:800;font-size:{int(h*.04)}px}} .b i{{width:{int(h*.05)}px;height:{int(h*.05)}px;border-radius:10px;background:{accent_css}}}
    h1{{font-size:{int(h*.085)}px;line-height:1.02;letter-spacing:-.035em;margin:{int(h*.04)}px 0 {int(h*.025)}px}}
    p{{font-size:{int(h*.028)}px;line-height:1.45;color:#aab3c0;margin:0}}
    .c{{display:flex;flex-wrap:wrap;gap:10px;margin-top:{int(h*.05)}px}} .c span{{border:1px solid #2a3240;background:#141821;border-radius:999px;padding:8px 16px;font-size:{int(h*.022)}px;font-weight:700}}
    .c span b{{color:{accent_css}}}
    .s{{position:absolute;right:-{int(w*.04)}px;top:{int(h*.12)}px;width:{int(w*.58)}px;border-radius:18px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 1px #2a3240;transform:perspective(1800px) rotateY(-9deg) rotateX(3deg)}}
    .s img{{display:block;width:100%}}</style></head><body><div class="g"></div><div class="glow"></div>
    <div class="s"><img src="{hero}"></div><div class="l"><div class="b"><i></i>{title}</div><h1>{tagline[0]}</h1><p>{tagline[1]}</p>
    <div class="c">{''.join(f'<span><b>{a}</b> {b}</span>' for a, b in chips)}</div></div></body></html>"""
    pg.set_viewport_size({"width": w, "height": h})
    pg.goto(base + "_cover.html") if False else None
    (WEB / "_cover.html").write_text(html, encoding="utf-8")
    pg.goto(base + "_cover.html", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(out), type="jpeg", quality=90)
    (WEB / "_cover.html").unlink()


CONFIG = {}


def gennemfoert(pg, base, tmp):
    shots = {}
    pg.goto(base + "projekt.html#G-K-10", wait_until="networkidle")
    pg.wait_for_function("window.G && G.ready", timeout=120000)
    pg.wait_for_timeout(2500)
    orb = orbit(pg, tmp / "orb", 10, 0.5, 1.0, 0.82)
    loop = orbit(pg, tmp / "loop", 8, 0.32, 0.95, 0.85, clip={"x": 0, "y": 102, "width": 940, "height": 798})
    pg.evaluate("G.frozen = false")
    pg.goto(base + "forespoergsel.html", wait_until="networkidle"); pg.click("#example"); pg.wait_for_timeout(900)
    pg.screenshot(path=str(tmp / "intake.png"), full_page=True)
    pg.click("#submit"); pg.wait_for_selector("#receipt[style*=flex]"); pg.wait_for_timeout(500)
    pg.screenshot(path=str(tmp / "receipt.png"))
    pg.evaluate("localStorage.clear()")
    pg.goto(base + "sager.html#BV-2026-0169", wait_until="networkidle"); pg.wait_for_timeout(1200)
    pg.screenshot(path=str(tmp / "case.png"), full_page=True)
    pg.click("#tamper"); pg.wait_for_selector(".badline"); pg.wait_for_timeout(400)
    pg.locator("#chainbox").scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=str(tmp / "tamper.png"))
    pg.goto(base + "tilbud.html", wait_until="networkidle"); pg.wait_for_timeout(700); pg.screenshot(path=str(tmp / "quote.png"))
    pg.goto(base + "udfoerelse.html#G-1-01", wait_until="networkidle"); pg.wait_for_timeout(700); pg.screenshot(path=str(tmp / "site.png"))
    pg.goto(base + "overblik.html", wait_until="networkidle"); pg.wait_for_timeout(900); pg.screenshot(path=str(tmp / "dash.png"), full_page=True)
    pg.goto(base + "verify.html", wait_until="networkidle"); pg.wait_for_timeout(600)
    pg.set_input_files("#files", str(WEB / "downloads" / "Gennemfoeringsregister.xlsx")); pg.wait_for_selector(".fr"); pg.wait_for_timeout(500)
    pg.locator("#drop").scroll_into_view_if_needed(); pg.wait_for_timeout(300); pg.screenshot(path=str(tmp / "verify.png"))
    pg.goto(base + "viden.html", wait_until="networkidle"); pg.wait_for_timeout(700); pg.fill("#q", "PVC-U 110"); pg.wait_for_timeout(300)
    pg.locator(".etarow").nth(2).click(); pg.wait_for_timeout(900); pg.locator("#q").scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=str(tmp / "kb.png"))
    pg.goto(base + "index.html", wait_until="networkidle"); pg.wait_for_timeout(900); pg.screenshot(path=str(tmp / "hub.png"))
    scenes = [(frames_seq(orb[:150]), "Hver gennemføring i modellen", "IFC → testet / afvigelse, med ETA, afsnit og side"),
              (frames_still(tmp / "intake.png", 5.5, "scroll"), "Struktureret forespørgsel", "Forhåndstjek mod 678 testede rækker, mens kunden skriver"),
              (frames_still(tmp / "receipt.png", 3.2), "Kvittering på sekunder", "Testede svar med det samme; resten fordeles Øst/Vest med frist"),
              (frames_still(tmp / "case.png", 5.5, "scroll"), "Sag med præcedens", "Afvigelsens signatur → tidligere afgørelser; 4-øjne-kontrol"),
              (frames_still(tmp / "tamper.png", 3.5), "Revisionsspor der ikke kan rettes stille", "SHA-256-kæde, verificeret i browseren"),
              (frames_still(tmp / "quote.png", 3.5), "Tilbud med varenumre", "Mængder med grundlag fra den testede løsning"),
              (frames_still(tmp / "site.png", 3.5), "Udførelse og kontrol", "Tjekliste fra ETA-rækken, foto, underskrift, kontrollant"),
              (frames_still(tmp / "dash.png", 4.5, "scroll"), "Ledelsesoverblik", "Gennemløbstid, afvigelser, regioner"),
              (frames_still(tmp / "verify.png", 4.0), "Hver leverance kan verificeres", "Træk en fil ind: SHA-256 mod manifestet, ingen upload"),
              (frames_seq(orb[150:]), "Gennemført 2.0", "Beslutningsstøtte · fiktive demonstrationsdata")]
    return dict(orbit=orb, loop=loop, scenes=scenes, accent=(240, 180, 41), accent_css="#f0b429", hero=tmp / "orb" / "f0040.png",
                title="Gennemført 2.0", tagline=("Fra forespørgsel til kontrolleret udførelse.", "Brandtætninger kontrolleret mod de testede opbygninger i ETA'erne: sagsgang, præcedens, 4-øjne-kontrol, verificerbare leverancer."),
                chips=[("678", "testede rækker"), ("59/59", "facitliste"), ("1.500/1.500", "browser = server"), ("SHA-256", "revisionsspor")],
                shots={"hub": "hub.png", "intake": "intake.png", "case": "case.png", "tamper": "tamper.png", "quote": "quote.png", "site": "site.png",
                       "dash": "dash.png", "verify": "verify.png", "kb": "kb.png", "receipt": "receipt.png"})


def isoleret(pg, base, tmp):
    pg.goto(base + "index.html", wait_until="networkidle")
    pg.wait_for_function("window.G && G.ready", timeout=120000)
    pg.wait_for_timeout(1500)
    orb = orbit(pg, tmp / "orb", 6, 0.45, 1.0, 0.84)
    pg.evaluate("G.frozen = false"); pg.evaluate("G.mode('loss')"); pg.wait_for_timeout(400)
    orb2 = orbit(pg, tmp / "orb2", 5, 0.4, 0.9, 0.8)
    pg.evaluate("G.frozen = false"); pg.evaluate("G.mode('status')"); pg.wait_for_timeout(300)
    loop = orbit(pg, tmp / "loop", 8, 0.32, 0.95, 0.85, clip={"x": 0, "y": 100, "width": 960, "height": 800})
    pg.evaluate("G.frozen = false")
    pg.evaluate("location.hash = 'K1'"); pg.wait_for_timeout(1200)
    pg.locator("details.more summary").first.click(); pg.wait_for_timeout(400)
    pg.locator("details.more").first.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=str(tmp / "trace.png"))
    pg.goto(base + "beregner.html#K1", wait_until="networkidle"); pg.wait_for_timeout(900); pg.screenshot(path=str(tmp / "calc.png"), full_page=True)
    pg.goto(base + "brand.html", wait_until="networkidle"); pg.wait_for_timeout(800); pg.screenshot(path=str(tmp / "fire.png"), full_page=True)
    pg.goto(base + "metode.html", wait_until="networkidle"); pg.wait_for_timeout(900); pg.screenshot(path=str(tmp / "method.png"), full_page=True)
    pg.goto(base + "audit.html", wait_until="networkidle"); pg.wait_for_timeout(900); pg.screenshot(path=str(tmp / "audit.png"))
    pg.goto(base + "verify.html", wait_until="networkidle"); pg.wait_for_timeout(500)
    pg.set_input_files("#files", str(WEB / "downloads" / "Isoleringsrapport_blok_c.pdf")); pg.wait_for_selector(".fr"); pg.wait_for_timeout(500)
    pg.screenshot(path=str(tmp / "verify.png"))
    scenes = [(frames_seq(orb), "Hele bygningens isolering, i 3D", "Hver strækning mod DS 452: opfylder, for tynd, uisoleret, kondens"),
              (frames_seq(orb2), "Varmetab pr. meter", "EN ISO 12241 med λ ved middeltemperaturen"),
              (frames_still(tmp / "trace.png", 4.5), "Hvert tal kan regnes efter", "Vis beregning: λ, R, h, q og U mod grænsen, kontrolleret mod rapportens tal"),
              (frames_still(tmp / "calc.png", 5.0, "scroll"), "Beregner", "Krav, kondens og økonomisk optimum på samme kurve"),
              (frames_still(tmp / "fire.png", 5.0, "scroll"), "Energi møder brand", "Efterisolering kontrolleret mod de testede brandtætninger"),
              (frames_still(tmp / "method.png", 6.0, "scroll"), "Valideret mod de publicerede tabeller", "DS 452 anneks A og Energihåndbogen, celle for celle"),
              (frames_still(tmp / "verify.png", 3.5), "Hver leverance kan verificeres", "SHA-256 mod manifestet, genberegning fra kildemodellen")]
    return dict(orbit=orb, loop=loop, scenes=scenes, accent=(45, 212, 191), accent_css="#2dd4bf", hero=tmp / "orb" / "f0030.png",
                title="Isoleret", tagline=("Teknisk isolering, hele bygningen.", "DS 452-klasse, varmetab efter EN ISO 12241, besparelse, kondens og et brandkrydstjek ved hver gennemføring."),
                chips=[("72/72", "DS 452 anneks A ≤ 3 mm"), ("25/25", "facitliste"), ("19", "brandkonflikter løst"), ("1e-9", "browser = server")],
                shots={"map": None, "trace": "trace.png", "calc": "calc.png", "fire": "fire.png", "method": "method.png", "audit": "audit.png", "verify": "verify.png"})


def main(product):
    OUT.mkdir(parents=True, exist_ok=True)
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    tmp = Path(tempfile.mkdtemp(prefix="media_"))
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="msedge", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, color_scheme="dark")
            pg = ctx.new_page()
            cfg = (gennemfoert if product == "gennemfoert" else isoleret)(pg, base, tmp)
            compose(cfg["scenes"], OUT / "tour.mp4", cfg["accent"])
            to_mp4(cfg["loop"], OUT / "loop.mp4")
            to_mp4(cfg["orbit"], OUT / "orbit.mp4")
            to_gif(OUT / "loop.mp4", OUT / "loop.gif", 640, 15)
            hero = WEB / "_hero.png"
            shutil.copy(cfg["hero"], hero)
            cpg = ctx.new_page()
            cover(cpg, base, "_hero.png", cfg["title"], cfg["tagline"], cfg["chips"], cfg["accent_css"], OUT / "cover.jpg", 1600, 900)
            cover(cpg, base, "_hero.png", cfg["title"], cfg["tagline"], cfg["chips"], cfg["accent_css"], OUT / "og.jpg", 1200, 630)
            hero.unlink()
            Image.open(cfg["hero"]).convert("RGB").save(OUT / "hero.jpg", quality=88)
            Image.open(cfg["loop"][0]).convert("RGB").save(OUT / "loop_poster.jpg", quality=85)
            for k, v in cfg["shots"].items():
                if v:
                    im = Image.open(tmp / v).convert("RGB")
                    if im.height > 2400:
                        im = im.crop((0, 0, im.width, 2400))
                    im.save(OUT / f"shot_{k}.jpg", quality=86)
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    for p in sorted(OUT.iterdir()):
        print(p.name, round(p.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main(sys.argv[1])
