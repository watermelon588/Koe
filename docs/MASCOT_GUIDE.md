# Making Koe's mascot in VRoid Studio

A step-by-step guide for building the mascot yourself. Keep it open next to VRoid Studio. Time: about **3–5 hours** the first time.
Menu names come from pixiv's official help center (VRoid Studio **v2.14.0**, Jun 2026). If a button has moved in your version, search the name in the [VRoid help center](https://vroid.pixiv.help/hc/en-us/categories/900000339606-VRoid-Studio-Stable-Ver).

---

## 0. What we're making

### The honest style note
Your references (`frontend/assets/mascot reference/`) are **stylized 3D**, Pixar/Arcane-like: soft painterly shading, a real nose, freckles, heavy-lidded eyes. VRoid makes **cel-shaded anime** by default (flat colours, hard shadow edge, outlines). We close most of the gap in two places:
1. **In VRoid:** pick a visible nose, paint freckles and blush, soften the eye shapes, choose muted colours (steps 3–5).
2. **In our code, after export:** VRoid models use the **MToon** shader, and three-vrm lets us soften it: smoother shadow gradient, no outline, no rim light. That's my job in the hand-off (step 10).

It won't look like a Blender sculpt, but it can look like a cute, soft 3D version of these girls.

### Design brief: what all your references share
| Feature | From the references | For Koe |
|---|---|---|
| Face | Round, soft jaw, pale skin, **pink-red ears**, blush across cheeks *and nose bridge*, **freckles** | Same |
| Eyes | Big, wide-set, warm brown or amber, slightly **sleepy upper lid**, individually drawn **lower lashes** | Same, which gives a calm, a little melancholic, very cute look |
| Brows | **Thick, straight, dark** even with light hair | Same |
| Nose / lips | Small rounded nose with a **pink tip**; small, full, rose lips | Same |
| Hair | **Short bob, blunt choppy bangs**, silver-white / lavender-grey | Chin-length silver-lavender bob, tucked behind the ears so they show |
| Head | Thick **headband** with pins/buttons (green, black) | Forest-green headband + 2 pearl pins |
| Outfit | **Oversized sweater**, high **turtleneck**, streetwear | Red turtleneck under an oversized mint (or cream) sweater; pleated skirt, knee socks, chunky shoes |
| Extra | **Wired earbuds**, dangling earrings | Earbud cable, a nod to Koe being a *voice* agent |

### Palette (hex codes for VRoid's colour pickers)
Sampled from your reference images, then brightened slightly: the samples sit in shadow, and VRoid's base colour is the *lit* colour.

| Part | Hex | Sampled from |
|---|---|---|
| Skin | `#F6E3DA` | forehead/cheeks (`e955…`, `b962…`) |
| Blush (cheeks + nose bridge) | `#E5B4B1` at ~50% opacity | `e955…` |
| Nose tip, ears | `#D9827F` | `b962…` (`#C2736F` in shade) |
| Lips | `#D8686A` | `b962…` (`#D35150`) |
| Hair main | `#E2D7E2` silver-lavender | `e955…` |
| Hair highlight / shade | `#B4A4AD` | `b962…` bangs |
| Brows | `#4A3430` | dark brown |
| Iris | `#5D3B39` warm brown → lighter `#9A6A55` at the bottom | `b962…` (amber alternative `#8A6A30`, `e955…`) |
| Headband | `#527367` forest green | `e955…` |
| Turtleneck | `#E9494B` | `b962…` |
| Sweater | `#A8B59D` mint, or `#E8D6BF` cream | `b962…` / `6d4a…` |
| Skirt | `#67383B` plaid wine | `b584…` |
| Earrings | `#1E1E1E` + gold `#D4A843` | `b962…` |

> The references include watermarked images (小红书, *Love and Deepspace*). Use them **as references only**; never ship them in the app.

---

## 1. Install and start
1. Install **VRoid Studio** (free, Windows): from [vroid.com/en/studio](https://vroid.com/en/studio) or Steam (search "VRoid Studio"). Check your laptop against the [operating requirements](https://vroid.pixiv.help/hc/en-us/articles/900006049066-Operating-environment-requirements).
2. Open it → **Create New** → pick the **female** base. You should see the tabs **Face · Hairstyle · Body · Outfit · Accessories** at the top.
   - ⚠️ If you land on an empty screen titled **"Dress-up Feature"** (Closet / Base Model / Costumes), you're in the wrong mode. Dress-up only re-dresses *existing* models, so it starts empty. Go back with the **☰** menu (top left) to the start screen and choose normal character creation.
3. **Save right away** as `koe.vroid` and press **Ctrl + S** often. ⚠️ A `.vrm` file **can't be opened back in VRoid Studio**, so the `.vroid` file is your only editable source. Keep it somewhere safe (it's a design file, not a repo file).
4. Tip: you can switch to the dark theme in settings, which is easier on the eyes for long sessions.

---

## 2. Body: chibi-leaning proportions
**Body** tab (everything below the neck, plus overall size).
1. Raise **head size** and lower **height** until she's about **4–5 heads tall**: cute and chibi-leaning, but still animating well.
2. Pixiv has an official article on exactly this: search **"Adjust the parameters to easily create a SD character"** in the [help center](https://vroid.pixiv.help/hc/en-us) (SD = super-deformed = chibi). Follow its slider values as a starting point.
3. Keep **arms and legs a normal-ish length**. Our code lowers the arms from the T-pose; very short arms clip into a big head or a wide sweater.
4. Don't over-polish the legs: the call screen frames **head and shoulders**, so the **face matters most**. Spend your time there.

---

## 3. Face: where most of the character lives
**Face** tab. The left column has 17 categories ([official article](https://vroid.pixiv.help/hc/en-us/articles/4406164546969-How-to-edit-faces)). Every category has **Color**, **Parameters** (position/size sliders) and **Edit Texture** (paint with a brush). Go in this order:

1. **Face Sets:** pick the softest, roundest preset as a base.
2. **Face shape parameters:** rounder cheeks, smaller chin, slightly wider face. Aim for the soft "baby face" of `e955…` and `b962…`.
3. **Eyes Sets:** pick a set with **large, round irises**, then refine each part:
   - **Irises:** colour `#5D3B39` with a lighter bottom `#9A6A55`; scale up a little.
   - **Eye Highlights:** one clear main highlight plus a small one (the references have a single sharp white dot).
   - **Scleras:** plain white, nothing fancy.
   - **Eyelid:** lower the upper lid slightly for the **calm, sleepy look**; it's the signature of your references.
   - **Eyeliner:** thin and dark, with a small flick at the outer corner (`b962…`).
   - **Eyelashes:** choose a style with **separate lower lashes**. If none fits, use **Edit Texture** and draw 4–6 short lines under each eye.
4. **Eyebrows:** **thick and straight**, colour `#4A3430`, set a little higher above the eyes.
5. **Nose:** pick a **visible, small, rounded** nose (not the anime dot). Use **Edit Texture** to tint the tip `#D9827F`.
6. **Mouth / Lips:** small and full; lip colour `#D8686A`. Check **Mouth Inside** looks okay, since the mouth opens when she talks.
7. **Cheeks:** blush `#E5B4B1`, wide, crossing the **nose bridge** (all your references do this).
8. **Skin:** `#F6E3DA`.
9. **Face Paint → Edit Texture**, on a **new layer**:
   - **Freckles:** a small soft brush, `#C98A7A` at ~40% opacity, dotted over the nose and upper cheeks. Fewer is cuter; copy `e955…`.
   - **Ear tint:** `#D9827F`, soft brush on the ears.
   - The **Sticker tool** (texture editor toolbar) can stamp any PNG at an adjustable opacity. Once stamped it's baked in; undo with **Ctrl + Z** ([how it works](https://vroid.pixiv.help/hc/en-us/articles/55426007561113-How-to-Use-the-Sticker-Tool)).

---

## 4. Hair: silver-lavender bob with blunt bangs
**Hairstyle** tab ([easy hair](https://vroid.pixiv.help/hc/en-us/articles/4405086656153-How-to-model-hair-easily), [custom hair](https://vroid.pixiv.help/hc/en-us/articles/900005678786-How-do-I-customize-hairstyles)).
1. **Hairstyle Sets:** pick a **short bob with bangs** as the base. You can swap the **front** (bangs) and **back** separately.
2. Bangs: **blunt and a bit choppy**, at eyebrow height (`b962…`, `b584…`). To reshape: **Edit Hairstyle** → **Retouch Brush**, stroking along the guide grid. **Control Point** changes length.
3. Sides: tuck behind the ears so the pink ears show (`e955…`).
4. Colours: **Main** `#E2D7E2`, **Highlight** `#B4A4AD`. For a softer look, pick an **Outline Color** close to the main colour so the outline almost disappears ([hair materials](https://vroid.pixiv.help/hc/en-us/articles/900005965706-How-to-edit-hair-color-and-texture-material)).
5. **Hair bounce** (makes her hair sway when she moves): select the hair → **Set Hair Bounce** → **Auto-generate Bone Group**. Use a **moderate count (6–10 groups)**: more bones look more fluid but cost more CPU every frame ([official article](https://vroid.pixiv.help/hc/en-us/articles/900006910023-I-want-to-edit-hair-bounce)). Preset hairstyles already have bounce set.

### The headband
**Accessories** tab → **Add Accessories**, and look for a hairband or headband. Position it with the **Gizmo** (move/scale/rotate), then **Change Colors** to `#527367` ([accessories tab](https://vroid.pixiv.help/hc/en-us/articles/900006965863-What-are-the-commands-on-the-Accessories-tab)).
- **If the list has no headband** (I couldn't confirm it does): VRoid users often build one out of hair. In **Hairstyle**, open the **Custom** tab, press **+**, then **Add Procedural Hair Guides**, shape it into a thick band across the top of the head, and give it its **own material** (the + next to the material name) in green.
- **Pearl pins:** small round accessories (or 2 tiny hair chunks) in `#F2EEE6`.

---

## 5. Outfit
**Outfit** tab: Tops, Bottoms, Dresses, Shoes and so on.
1. **Tops:** a **turtleneck / high-neck** top in `#E9494B` + an **oversized sweater** in mint `#A8B59D`. If you can't layer them, pick one high-neck sweater and paint a red collar band with **Edit Texture**.
2. Knit feel: **Edit Texture** with a fine vertical-line brush at low opacity on the cuffs and hem (`6d4a…`, `b584…`).
3. 🎌 **Brand touch:** use the **Sticker tool** to put a small **声** patch on the chest or sleeve.
4. **Bottoms:** pleated skirt `#67383B`; **knee socks** white; **chunky black shoes**.
5. ⚠️ Use the **normal Outfit tab**, not the separate *Dress-up feature* (XWear items). Pixiv lists a known issue: models with **multi-UV materials can't be exported as VRM**.

### Earrings and earbuds
**Accessories** → dangling earrings (`#1E1E1E` + gold `#D4A843`). For the **wired earbuds** (`b962…`): if there's no ready item, a thin dark hair strand from each ear down to the collar sells the look.

---

## 6. Expressions: how she reacts in calls
**Face** tab → the **Expression Editor** (the last icon in the left list) ([official article](https://vroid.pixiv.help/hc/en-us/articles/4408150140825-How-to-use-the-Expression-Editor)). Pick a preset on the left, then use the sliders to move brows, eyes and mouth.

| Expression | What to set | Koe uses it for |
|---|---|---|
| **Neutral** | Calm, slightly sleepy lids, tiny closed smile | idle / listening |
| **Happy** (Joy) | Eyes curve up, cheeks lift, mouth smiles | an action succeeded |
| **Sad** (Sorrow) | Inner brows up, eyes soften | error |
| **Surprised** | Brows up, eyes wide, small "o" mouth | new alert |
| **Relaxed** (Fun) | Soft half-closed eyes, gentle smile | thinking |
| **Angry** | Keep it mild; she's cute | rarely |

- The **mouth shapes (A, I, U, E, O)** and **blink** are what our lip-sync code drives. Check that **A** opens the mouth nicely; if your version lets you edit it, make it a little rounder.
- The NEUTRAL expression is the face's default look, not "all sliders at 0".
- Test expressions in the **Photo Booth** tab.

---

## 7. Check in Photo Booth
**Photo Booth** tab: play a few **poses and animations**. Look for:
- hair or headband **clipping** into the face when the head turns;
- sweater sleeves exploding when the arms go down (our code holds the arms at the sides; test a "standing" pose);
- the face from a **slightly low and front angle**, which is how the call screen sees her.

---

## 8. Export as VRM
Export icon (top right) → **Export VRM** ([official article](https://vroid.pixiv.help/hc/en-us/articles/15760756822297-I-want-to-learn-more-about-the-VRM-export-feature)).
1. On the export page you can **reduce polygons, materials and bones**. For the web:
   - **Reduce materials: yes.** Fewer materials = fewer draw calls = cheaper frames.
   - **Polygons:** mild reduction; check the face still looks smooth.
   - **Bones:** keep the hair bones (that's the bounce).
   - **Texture quality:** start at the default. If the file is **> 15 MB**, export again at a lower texture size. The sample model is 10.8 MB; aim for about that.
2. Click **Export** → choose **VRM 1.0** (our code targets it; 0.0 also works).
3. Fill in **Avatar name**: `Koe` (or her name, once we pick one), **Creator**: `Rohit Maity`. Choose the permissions you want; it's your character.
4. Save as **`koe.vrm`** in `frontend/public/mascot/`.

The expression parameters show as 0 on the export screen; that's normal, and your expressions are still saved in the file.

---

## 9. Checklist before you hand it over
- [ ] `koe.vroid` saved somewhere safe (the editable source)
- [ ] `frontend/public/mascot/koe.vrm` exists, ideally ≤ 15 MB
- [ ] Mouth opens with **A**; she blinks; Happy / Sad / Surprised / Relaxed look right in Photo Booth
- [ ] Hair bounces without clipping into the face
- [ ] Head-and-shoulders view looks good (that's 90% of what users see)

## 10. Hand-off: what I do next
Tell me when `koe.vrm` is in place, and I'll:
1. Point the mascot at `koe.vrm` (one line) and re-frame the camera for her proportions.
2. **Soften the MToon shading in code** toward your references: smoother shadow gradient, outline off, rim light off.
3. Map the expressions to call states (thinking → Relaxed, success → Happy, error → Sad).
4. Re-measure file size, load time and frame cost, and log them in BUILD_LOG.

## Sources
- VRoid help center (official): [Stable Ver. index](https://vroid.pixiv.help/hc/en-us/categories/900000339606-VRoid-Studio-Stable-Ver) · [faces](https://vroid.pixiv.help/hc/en-us/articles/4406164546969-How-to-edit-faces) · [hair](https://vroid.pixiv.help/hc/en-us/articles/900005678786-How-do-I-customize-hairstyles) · [hair bounce](https://vroid.pixiv.help/hc/en-us/articles/900006910023-I-want-to-edit-hair-bounce) · [accessories](https://vroid.pixiv.help/hc/en-us/articles/900006965863-What-are-the-commands-on-the-Accessories-tab) · [sticker tool](https://vroid.pixiv.help/hc/en-us/articles/55426007561113-How-to-Use-the-Sticker-Tool) · [expression editor](https://vroid.pixiv.help/hc/en-us/articles/4408150140825-How-to-use-the-Expression-Editor) · [VRM export](https://vroid.pixiv.help/hc/en-us/articles/15760756822297-I-want-to-learn-more-about-the-VRM-export-feature) · [commercial use of your models](https://vroid.pixiv.help/hc/en-us/articles/4405813333657-Can-I-use-the-models-created-with-VRoid-Studio-Stable-Ver-for-commercial-purposes)
- Chibi limits in VRM pipelines (third-party): [CineV guide](https://docs.channel.io/cinev/en/articles/Creating-a-VRM-Character-f48ad4d9)
