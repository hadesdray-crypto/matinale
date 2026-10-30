# Essai réel du moteur de voix téléchargeables (sur le serveur GitHub, qui a Internet).
import asyncio, base64, json, sys, time
from playwright.async_api import async_playwright
OUT = sys.argv[1]
JS_TEL = """async (id) => { const t0 = performance.now(); let last = 0, n = 0;
  await VoixPiper.telecharger(id, (f, txt) => { n++; last = f; });
  return { s: Math.round(performance.now() - t0) / 1000, progressions: n, fin: last, etat: await VoixPiper.etat() }; }"""
JS_SYN = """async ([id, text, spk]) => { const r = await VoixPiper.fabriquer(id, text, spk == null ? {} : { speaker: spk });
  const b = new Uint8Array(await r.blob.arrayBuffer()); let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768));
  return { ms: r.ms, dur: r.dur, wav: btoa(s) }; }"""
PHRASES = ["Bonjour, voici la météo à Louviers : six degrés, ciel couvert, pluie jusqu'à dix-huit heures.",
           "Le télescope James-Webb révèle de fortes disparités atmosphériques sur une exoplanète.",
           "Tu as un trajet ce matin ?"]
async def main():
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx = await b.new_context()
        pg = await ctx.new_page(); logs = []
        pg.on('console', lambda m: logs.append(m.text[:300])); pg.on('pageerror', lambda e: logs.append('ERR ' + str(e)[:300]))
        await pg.goto('http://localhost:8000/essai.html'); await pg.wait_for_timeout(500)
        res['etat0'] = await pg.evaluate("VoixPiper.etat()")
        for vid, spk in [('fr_FR-siwis-low', None), ('fr_FR-gilles-low', None), ('fr_FR-tom-medium', None), ('fr_FR-mls-medium', 7)]:
            r = {}
            try:
                r['telechargement'] = await pg.evaluate(JS_TEL, vid)
                r['test'] = await pg.evaluate("id => VoixPiper.tester(id)", vid)
                syn = []
                for i, t in enumerate(PHRASES):
                    x = await pg.evaluate(JS_SYN, [vid, t, spk])
                    fn = f"{OUT}/{vid.replace('#', '_')}-{i}.wav"; open(fn, 'wb').write(base64.b64decode(x['wav']))
                    syn.append({'ms': x['ms'], 'dur': round(x['dur'], 2), 'fichier': fn.split('/')[-1]})
                r['phrases'] = syn
            except Exception as e:
                r['erreur'] = str(e)[:500]
            res[vid] = r
        # hors connexion : on recharge la page sans réseau, la voix doit marcher depuis le téléphone
        await ctx.set_offline(True)
        await pg.evaluate("() => { VoixPiper.arreter(); }")
        try:
            x = await pg.evaluate("async () => { const r = await VoixPiper.fabriquer('fr_FR-siwis-low', 'Sans Internet, la voix marche quand même. Deuxième phrase pour vérifier.', {}); const b = new Uint8Array(await r.blob.arrayBuffer()); let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return { ms: r.ms, dur: r.dur, wav: btoa(s) }; }")
            open(f"{OUT}/hors-ligne.wav", 'wb').write(base64.b64decode(x['wav'])); res['hors_ligne'] = {'ms': x['ms'], 'dur': round(x['dur'], 2)}
        except Exception as e:
            res['hors_ligne'] = 'ERREUR ' + str(e)[:300]
        await ctx.set_offline(False)
        res['effacer'] = await pg.evaluate("async () => { await VoixPiper.effacer('fr_FR-tom-medium'); return VoixPiper.etat(); }")
        res['place'] = await pg.evaluate("VoixPiper.place()")
        res['echantillon'] = await pg.evaluate("async () => { const r = await fetch('https://rhasspy.github.io/piper-samples/samples/fr/fr_FR/siwis/medium/speaker_0.mp3', { mode:'no-cors' }); return r.type + ' ' + r.status; }")
        res['logs'] = logs[-30:]
        await b.close()
    json.dump(res, open(f'{OUT}/resultats.json', 'w'), ensure_ascii=False, indent=1)
asyncio.run(main())
