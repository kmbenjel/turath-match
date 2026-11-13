# turath-match demo

10 catalog records checked against 10 library books.

| Status | الحالة | Records |
|---|---|---:|
| Have | موجود | 4 |
| Partial | ناقص الأجزاء | 0 |
| Have the work | الكتاب موجود والطبعة غير مؤكدة | 0 |
| Other edition | طبعة أخرى | 2 |
| Related work only | عمل متصل به فقط | 1 |
| Review | للمراجعة | 1 |
| Missing | مفقود | 2 |

## Have · موجود (4)

- **مقدمة ابن خلدون** — عبد الرحمن بن محمد بن خلدون `wishlist:W01`  
  library: المقدمة (ابن خلدون)  
  work · same · high (0.92) via `exact_title_author`: exact: same one-word title «مقدمة ابن خلدون» / «المقدمة»; same: «عبد الرحمن بن محمد بن خلدون» / «ابن خلدون» (shuhra:ابن خلدون)  
  file: Muqaddima-scan.pdf is `archive:AAlexandrina-164114` (164114 - مقدمة العلامة ابن خلدون.pdf, exact size)
- **طوق الحمامة** — ابن حزم `wishlist:W04`  
  library: طوق الحمامة في الألفة والألاف (ابن حزم الأندلسي)  
  edition · same · high (0.85) via `fuzzy_title_author`: same editor: «إحسان عباس» / «إحسان عباس»; the editor is all the other record says about its edition
- **كليلة ودمنة** — عبد الله بن المقفع `wishlist:W05`  
  library: كتاب كليلة ودمنة ("إبن المقفع، عبد الله")  
  work · same · high (0.97) via `exact_title_author`: exact: same title words «كليلة ودمنة» / «كتاب كليلة ودمنة»; same: «عبد الله بن المقفع» / «"إبن المقفع، عبد الله"» (ism:عبد الله, nasab:المقفع); the author of library:L05 is read from archive:AAlexandrina-144704, the source of its file (exact size)  
  file: kalila.pdf is `archive:AAlexandrina-144704` (144704 - كتاب كليلة ودمنة.pdf, exact size)
- **الجامع المسند الصحيح = صحيح البخاري** — محمد بن إسماعيل البخاري `wishlist:W08`  
  library: صحيح البخاري (البخاري)  
  work · same · high (0.92) via `exact_title_author`: exact: same one-word title «الجامع المسند الصحيح = صحيح البخاري» / «صحيح البخاري»; same: «محمد بن إسماعيل البخاري» / «البخاري» (nisba:البخاري)

## Other edition · طبعة أخرى (2)

- **رسالة الغفران** — أبو العلاء المعري `wishlist:W02`  
  library: رسالة الغفران (أبو العلاء المعري)  
  edition · different · high (0.95) via `fuzzy_title_author`: different editors: «عائشة عبد الرحمن» / «كامل كيلاني»; years differ: 1950 / 1923 (another printing)  
  copy: [رسالة الغفران أبي العلاء المعري](https://archive.org/details/elshandawily10111) `archive:elshandawily10111`, 1 file(s), 51,221,406 bytes  
  copy: [رسالة الغفران](https://github.com/OpenITI/0450AH/blob/master/data/0449AbuCalaMacarri/0449AbuCalaMacarri.RisalatGhufran/0449AbuCalaMacarri.RisalatGhufran.Shamela0001589-ara1) `openiti:0449AbuCalaMacarri.RisalatGhufran.Shamela0001589-ara1`  
  copy: [رسالة الغفران](https://github.com/OpenITI/0450AH/blob/master/data/0449AbuCalaMacarri/0449AbuCalaMacarri.RisalatGhufran/0449AbuCalaMacarri.RisalatGhufran.JK009234-ara1) `openiti:0449AbuCalaMacarri.RisalatGhufran.JK009234-ara1`
- **البيان والتبيين** — أبو عثمان عمرو بن بحر الجاحظ `wishlist:W06`  
  library: البيان والتبيين (الجاحظ)  
  edition · different · high (0.90) via `fuzzy_title_author`: different publishers: «مكتبة الخانجي» / «المطبعة العلمية»; years differ: 1418 هـ / 1311 (another printing)  
  copy: [البيان والتبيين](https://github.com/OpenITI/0275AH/blob/master/data/0255Jahiz/0255Jahiz.BayanWaTabyin/0255Jahiz.BayanWaTabyin.JK001009-ara1) `openiti:0255Jahiz.BayanWaTabyin.JK001009-ara1`  
  copy: [البيان والتبيين = البيان والتبيين - ط صعب](https://github.com/OpenITI/0275AH/blob/master/data/0255Jahiz/0255Jahiz.BayanWaTabyin/0255Jahiz.BayanWaTabyin.ShamAY0033779-ara1) `openiti:0255Jahiz.BayanWaTabyin.ShamAY0033779-ara1`  
  copy: [البيان والتبيين - ط الخانجي = البيان والتبيين](https://github.com/OpenITI/0275AH/blob/master/data/0255Jahiz/0255Jahiz.BayanWaTabyin/0255Jahiz.BayanWaTabyin.ShamAY0033801-ara1) `openiti:0255Jahiz.BayanWaTabyin.ShamAY0033801-ara1`

## Related work only · عمل متصل به فقط (1)

- **ديوان المتنبي** — أبو الطيب المتنبي `wishlist:W03`  
  work · related · medium (0.70) via `fuzzy_title_author`: related: «شرح» makes it a commentary «ديوان المتنبي» / «شرح ديوان المتنبي»; different: «أبو الطيب المتنبي» / «عبد الرحمن البرقوقي» (nisba-conflict:المتنبي!=البرقوقي); commentary: the right record is built on the other  
  related: شرح ديوان المتنبي — commentary  
  copy: [ديوان المتنبي](https://github.com/OpenITI/0375AH/blob/master/data/0354Mutanabbi/0354Mutanabbi.Diwan/0354Mutanabbi.Diwan.JK007610-ara1) `openiti:0354Mutanabbi.Diwan.JK007610-ara1`  
  copy: [ديوان المتنبي](https://github.com/OpenITI/0375AH/blob/master/data/0354Mutanabbi/0354Mutanabbi.Diwan/0354Mutanabbi.Diwan.ShamAY0037830-ara1) `openiti:0354Mutanabbi.Diwan.ShamAY0037830-ara1`

## Review · للمراجعة (1)

- **الرسالة** — محمد بن إدريس الشافعي `wishlist:W07`  
  library: الرسالة (محمد)  
  work · uncertain · low (0.45) via `exact_title_author`: exact: same one-word title «الرسالة» / «الرسالة»; unknown: «محمد بن إدريس الشافعي» / «محمد» (only-common-tokens, ism:محمد); the authors are not shown to be one person nor two: the title alone cannot prove the work

## Missing · مفقود (2)

- **تهافت الفلاسفة** — أبو حامد الغزالي `wishlist:W09`  
  copy: [تهافت الفلاسفة](https://github.com/OpenITI/0525AH/blob/master/data/0505Ghazali/0505Ghazali.Tahafut/0505Ghazali.Tahafut.Shamela0011055-ara1) `openiti:0505Ghazali.Tahafut.Shamela0011055-ara1`
- **الكامل في اللغة والأدب** — المبرد `wishlist:W10`  
  copy: [الكامل في للغة والأدب](https://github.com/OpenITI/0300AH/blob/master/data/0285IbnYazidMubarrad/0285IbnYazidMubarrad.KamilFiLugha/0285IbnYazidMubarrad.KamilFiLugha.Shamela0008505-ara1) `openiti:0285IbnYazidMubarrad.KamilFiLugha.Shamela0008505-ara1` — same edition  
  copy: [الكامل في للغة والأدب](https://github.com/OpenITI/0300AH/blob/master/data/0285IbnYazidMubarrad/0285IbnYazidMubarrad.KamilFiLugha/0285IbnYazidMubarrad.KamilFiLugha.Zaydiyya0000578-ara1) `openiti:0285IbnYazidMubarrad.KamilFiLugha.Zaydiyya0000578-ara1` — same edition  
  copy: [الكامل في للغة والأدب](https://github.com/OpenITI/0300AH/blob/master/data/0285IbnYazidMubarrad/0285IbnYazidMubarrad.KamilFiLugha/0285IbnYazidMubarrad.KamilFiLugha.ShamIbadiyya0000642-ara1) `openiti:0285IbnYazidMubarrad.KamilFiLugha.ShamIbadiyya0000642-ara1`

## Review list (1)

| left | right | score | why |
|---|---|---:|---|
| الرسالة | الرسالة | 0.45 | exact: same one-word title «الرسالة» / «الرسالة»; unknown: «محمد بن إدريس الشافعي» / «محمد» (only-common-tokens, ism:محمد); the authors are not shown to be one person nor two: the title alone cannot prove the work |

## Library files identified by their bytes only (1)

- تهافت الفلاسفة — علاء الدين الطوسي: `tusi-tahafut.pdf` is `archive:TahafutFalasifaAlaDinTussi` «تهافت الفلاسفة - علاء الدين الطّوسي»  (exact_size, 0.95)

## Library books not found in any catalog (1)

- مذكرات رحلة الحج — ?
