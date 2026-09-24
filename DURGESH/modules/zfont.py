from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from DURGESH import app

FONTS_DATA = {
    'typewriter': '𝚊\x01𝚋\x01𝚌\x01𝚍\x01𝚎\x01𝚏\x01𝚐\x01𝚑\x01𝚒\x01𝚓\x01𝚔\x01𝚕\x01𝚖\x01𝚗\x01𝚘\x01𝚙\x01𝚚\x01𝚛\x01𝚜\x01𝚝\x01𝚞\x01𝚟\x01𝚠\x01𝚡\x01𝚢\x01𝚣\x01𝙰\x01𝙱\x01𝙲\x01𝙳\x01𝙴\x01𝙵\x01𝙶\x01𝙷\x01𝙸\x01𝙹\x01𝙺\x01𝙻\x01𝙼\x01𝙽\x01𝙾\x01𝙿\x01𝚀\x01𝚁\x01𝚂\x01𝚃\x01𝚄\x01𝚅\x01𝚆\x01𝚇\x01𝚈\x01𝚉',
    'outline': '𝕒\x01𝕓\x01𝕔\x01𝕕\x01𝕖\x01𝕗\x01𝕘\x01𝕙\x01𝕚\x01𝕛\x01𝕜\x01𝕝\x01𝕞\x01𝕟\x01𝕠\x01𝕡\x01𝕢\x01𝕣\x01𝕤\x01𝕥\x01𝕦\x01𝕧\x01𝕨\x01𝕩\x01𝕪\x01𝕫\x01𝔸\x01𝔹\x01ℂ\x01𝔻\x01𝔼\x01𝔽\x01𝔾\x01ℍ\x01𝕀\x01𝕁\x01𝕂\x01𝕃\x01𝕄\x01ℕ\x01𝕆\x01ℙ\x01ℚ\x01ℝ\x01𝕊\x01𝕋\x01𝕌\x01𝕍\x01𝕎\x01𝕏\x01𝕐\x01ℤ\x01𝟘\x01𝟙\x01𝟚\x01𝟛\x01𝟜\x01𝟝\x01𝟞\x01𝟟\x01𝟠\x01𝟡',
    'serief': '𝐚\x01𝐛\x01𝐜\x01𝐝\x01𝐞\x01𝐟\x01𝐠\x01𝐡\x01𝐢\x01𝐣\x01𝐤\x01𝐥\x01𝐦\x01𝐧\x01𝐨\x01𝐩\x01𝐪\x01𝐫\x01𝐬\x01𝐭\x01𝐮\x01𝐯\x01𝐰\x01𝐱\x01𝐲\x01𝐳\x01𝐀\x01𝐁\x01𝐂\x01𝐃\x01𝐄\x01𝐅\x01𝐆\x01𝐇\x01𝐈\x01𝐉\x01𝐊\x01𝐋\x01𝐌\x01𝐍\x01𝐎\x01𝐏\x01𝐐\x01𝐑\x01𝐒\x01𝐓\x01𝐔\x01𝐕\x01𝐖\x01𝐗\x01𝐘\x01𝐙\x01𝟎\x01𝟏\x01𝟐\x01𝟑\x01𝟒\x01𝟓\x01𝟔\x01𝟕\x01𝟖\x01𝟗',
    'bold_cool': '𝒂\x01𝒃\x01𝒄\x01𝒅\x01𝒆\x01𝒇\x01𝒈\x01𝒉\x01𝒊\x01𝒋\x01𝒌\x01𝒍\x01𝒎\x01𝒏\x01𝒐\x01𝒑\x01𝒒\x01𝒓\x01𝒔\x01𝒕\x01𝒖\x01𝒗\x01𝒘\x01𝒙\x01𝒚\x01𝒛\x01𝑨\x01𝑩\x01𝑪\x01𝑫\x01𝑬\x01𝑭\x01𝑮\x01𝑯\x01𝑰\x01𝑱\x01𝑲\x01𝑳\x01𝑴\x01𝑵\x01𝑶\x01𝑷\x01𝑸\x01𝑹\x01𝑺\x01𝑻\x01𝑼\x01𝑽\x01𝑾\x01𝑿\x01𝒀\x01𝒁',
    'cool': '𝑎\x01𝑏\x01𝑐\x01𝑑\x01𝑒\x01𝑓\x01𝑔\x01ℎ\x01𝑖\x01𝑗\x01𝑘\x01𝑙\x01𝑚\x01𝑛\x01𝑜\x01𝑝\x01𝑞\x01𝑟\x01𝑠\x01𝑡\x01𝑢\x01𝑣\x01𝑤\x01𝑥\x01𝑦\x01𝑧\x01𝐴\x01𝐵\x01𝐶\x01𝐷\x01𝐸\x01𝐹\x01𝐺\x01𝐻\x01𝐼\x01𝐽\x01𝐾\x01𝐿\x01𝑀\x01𝑁\x01𝑂\x01𝑃\x01𝑄\x01𝑅\x01𝑆\x01𝑇\x01𝑈\x01𝑉\x01𝑊\x01𝑋\x01𝑌\x01𝑍',
    'randi': 'ᴧ\x01ʙ\x01ᴄ\x01ᴅ\x01є\x01ꜰ\x01ɢ\x01ʜ\x01ɪ\x01ᴊ\x01ᴋ\x01ʟ\x01ϻ\x01η\x01σ\x01ᴘ\x01ǫ\x01ʀ\x01ꜱ\x01ᴛ\x01ᴜ\x01ᴠ\x01ᴡ\x01x\x01y\x01ᴢ\x01ᴧ\x01ʙ\x01ᴄ\x01ᴅ\x01є\x01ꜰ\x01ɢ\x01ʜ\x01ɪ\x01ᴊ\x01ᴋ\x01ʟ\x01ϻ\x01η\x01σ\x01ᴘ\x01ǫ\x01ʀ\x01ꜱ\x01ᴛ\x01ᴜ\x01ᴠ\x01ᴡ\x01x\x01y\x01ᴢ',
    'randava': 'ᴧ\x01ʙ\x01ᴄ\x01ᴅ\x01є\x01Ŧ\x01ɢ\x01ʜ\x01¡\x01ᴊ\x01ҡ\x01ʟ\x01ϻ\x01η\x01σ\x01ᴘ\x01ǫ\x01ʀ\x01ѕ\x01†\x01µ\x01ѵ\x01ω\x01א\x01γ\x01ƶ\x01ᴧ\x01ʙ\x01ᴄ\x01ᴅ\x01є\x01Ŧ\x01ɢ\x01ʜ\x01¡\x01ᴊ\x01ҡ\x01ʟ\x01ϻ\x01η\x01σ\x01ᴘ\x01ǫ\x01ʀ\x01ѕ\x01†\x01µ\x01ѵ\x01ω\x01א\x01γ\x01ƶ',
    'smallcap': 'ᴀ\x01ʙ\x01ᴄ\x01ᴅ\x01ᴇ\x01ғ\x01ɢ\x01ʜ\x01ɪ\x01ɪ\x01ᴋ\x01ʟ\x01ᴍ\x01ɴ\x01ᴏ\x01ᴘ\x01ǫ\x01ʀ\x01s\x01ᴛ\x01ᴜ\x01ᴠ\x01ᴡ\x01x\x01ʏ\x01ᴢ\x01A\x01B\x01C\x01D\x01E\x01F\x01G\x01H\x01I\x01J\x01K\x01L\x01M\x01N\x01O\x01P\x01Q\x01R\x01S\x01T\x01U\x01V\x01W\x01X\x01Y\x01Z\x01𝟶\x01𝟷\x01𝟸\x01𝟹\x01𝟺\x01𝟻\x01𝟼\x01𝟽\x01𝟾\x01𝟿',
    'script': '𝒶\x01𝒷\x01𝒸\x01𝒹\x01ℯ\x01𝒻\x01ℊ\x01𝒽\x01𝒾\x01𝒿\x01𝓀\x01𝓁\x01𝓂\x01𝓃\x01ℴ\x01𝓅\x01𝓆\x01𝓇\x01𝓈\x01𝓉\x01𝓊\x01𝓋\x01𝓌\x01𝓍\x01𝓎\x01𝓏\x01𝒜\x01ℬ\x01𝒞\x01𝒟\x01ℰ\x01ℱ\x01𝒢\x01ℋ\x01ℐ\x01𝒥\x01𝒦\x01ℒ\x01ℳ\x01𝒩\x01𝒪\x01𝒫\x01𝒬\x01ℛ\x01𝒮\x01𝒯\x01𝒰\x01𝒱\x01𝒲\x01𝒳\x01𝒴\x01𝒵',
    'bold_script': '𝓪\x01𝓫\x01𝓬\x01𝓭\x01𝓮\x01𝓯\x01𝓰\x01𝓱\x01𝓲\x01𝓳\x01𝓴\x01𝓵\x01𝓶\x01𝓷\x01𝓸\x01𝓹\x01𝓺\x01𝓻\x01𝓼\x01𝓽\x01𝓾\x01𝓿\x01𝔀\x01𝔁\x01𝔂\x01𝔃\x01𝓐\x01𝓑\x01𝓒\x01𝓓\x01𝓔\x01𝓕\x01𝓖\x01𝓗\x01𝓘\x01𝓙\x01𝓚\x01𝓛\x01𝓜\x01𝓝\x01𝓞\x01𝓟\x01𝓠\x01𝓡\x01𝓢\x01𝓣\x01𝓤\x01𝓥\x01𝓦\x01𝓧\x01𝓨\x01𝓩',
    'tiny': 'ᵃ\x01ᵇ\x01ᶜ\x01ᵈ\x01ᵉ\x01ᶠ\x01ᵍ\x01ʰ\x01ⁱ\x01ʲ\x01ᵏ\x01ˡ\x01ᵐ\x01ⁿ\x01ᵒ\x01ᵖ\x01ᵠ\x01ʳ\x01ˢ\x01ᵗ\x01ᵘ\x01ᵛ\x01ʷ\x01ˣ\x01ʸ\x01ᶻ\x01ᵃ\x01ᵇ\x01ᶜ\x01ᵈ\x01ᵉ\x01ᶠ\x01ᵍ\x01ʰ\x01ⁱ\x01ʲ\x01ᵏ\x01ˡ\x01ᵐ\x01ⁿ\x01ᵒ\x01ᵖ\x01ᵠ\x01ʳ\x01ˢ\x01ᵗ\x01ᵘ\x01ᵛ\x01ʷ\x01ˣ\x01ʸ\x01ᶻ',
    'comic': 'ᗩ\x01ᗷ\x01ᑕ\x01ᗪ\x01ᗴ\x01ᖴ\x01ᘜ\x01ᕼ\x01I\x01ᒍ\x01K\x01ᒪ\x01ᗰ\x01ᑎ\x01O\x01ᑭ\x01ᑫ\x01ᖇ\x01Տ\x01T\x01ᑌ\x01ᐯ\x01ᗯ\x01᙭\x01Y\x01ᘔ\x01ᗩ\x01ᗷ\x01ᑕ\x01ᗪ\x01ᗴ\x01ᖴ\x01ᘜ\x01ᕼ\x01I\x01ᒍ\x01K\x01ᒪ\x01ᗰ\x01ᑎ\x01O\x01ᑭ\x01ᑫ\x01ᖇ\x01Տ\x01T\x01ᑌ\x01ᐯ\x01ᗯ\x01᙭\x01Y\x01ᘔ',
    'san': '𝗮\x01𝗯\x01𝗰\x01𝗱\x01𝗲\x01𝗳\x01𝗴\x01𝗵\x01𝗶\x01𝗷\x01𝗸\x01𝗹\x01𝗺\x01𝗻\x01𝗼\x01𝗽\x01𝗾\x01𝗿\x01𝘀\x01𝘁\x01𝘂\x01𝘃\x01𝘄\x01𝘅\x01𝘆\x01𝘇\x01𝗔\x01𝗕\x01𝗖\x01𝗗\x01𝗘\x01𝗙\x01𝗚\x01𝗛\x01𝗜\x01𝗝\x01𝗞\x01𝗟\x01𝗠\x01𝗡\x01𝗢\x01𝗣\x01𝗤\x01𝗥\x01𝗦\x01𝗧\x01𝗨\x01𝗩\x01𝗪\x01𝗫\x01𝗬\x01𝗭\x01𝟬\x01𝟭\x01𝟮\x01𝟯\x01𝟰\x01𝟱\x01𝟲\x01𝟳\x01𝟴\x01𝟵',
    'slant_san': '𝙖\x01𝙗\x01𝙘\x01𝙙\x01𝙚\x01𝙛\x01𝙜\x01𝙝\x01𝙞\x01𝙟\x01𝙠\x01𝙡\x01𝙢\x01𝙣\x01𝙤\x01𝙥\x01𝙦\x01𝙧\x01𝙨\x01𝙩\x01𝙪\x01𝙫\x01𝙬\x01𝙭\x01𝙮\x01𝙯\x01𝘼\x01𝘽\x01𝘾\x01𝘿\x01𝙀\x01𝙁\x01𝙂\x01𝙃\x01𝙄\x01𝙅\x01𝙆\x01𝙇\x01𝙈\x01𝙉\x01𝙊\x01𝙋\x01𝙌\x01𝙍\x01𝙎\x01𝙏\x01𝙐\x01𝙑\x01𝙒\x01𝙓\x01𝙔\x01𝙕',
    'slant': '𝘢\x01𝘣\x01𝘤\x01𝘥\x01𝘦\x01𝘧\x01𝘨\x01𝘩\x01𝘪\x01𝘫\x01𝘬\x01𝘭\x01𝘮\x01𝘯\x01𝘰\x01𝘱\x01𝘲\x01𝘳\x01𝘴\x01𝘵\x01𝘶\x01𝘷\x01𝘸\x01𝘹\x01𝘺\x01𝘻\x01𝘈\x01𝘉\x01𝘊\x01𝘋\x01𝘌\x01𝘍\x01𝘎\x01𝘏\x01𝘐\x01𝘑\x01𝘒\x01𝘓\x01𝘔\x01𝘕\x01𝘖\x01𝘗\x01𝘘\x01𝘙\x01𝘚\x01𝘛\x01𝘜\x01𝘝\x01𝘞\x01𝘟\x01𝘠\x01𝘡',
    'sim': '𝖺\x01𝖻\x01𝖼\x01𝖽\x01𝖾\x01𝖿\x01𝗀\x01𝗁\x01𝗂\x01𝗃\x01𝗄\x01𝗅\x01𝗆\x01𝗇\x01𝗈\x01𝗉\x01𝗊\x01𝗋\x01𝗌\x01𝗍\x01𝗎\x01𝗏\x01𝗐\x01𝗑\x01𝗒\x01𝗓\x01𝖠\x01𝖡\x01𝖢\x01𝖣\x01𝖤\x01𝖥\x01𝖦\x01𝖧\x01𝖨\x01𝖩\x01𝖪\x01𝖫\x01𝖬\x01𝖭\x01𝖮\x01𝖯\x01𝖰\x01𝖱\x01𝖲\x01𝖳\x01𝖴\x01𝖵\x01𝖶\x01𝖷\x01𝖸\x01𝖹',
    'circles': 'Ⓐ︎\x01Ⓑ︎\x01Ⓒ︎\x01Ⓓ︎\x01Ⓔ︎\x01Ⓕ︎\x01Ⓖ︎\x01Ⓗ︎\x01Ⓘ︎\x01Ⓙ︎\x01Ⓚ︎\x01Ⓛ︎\x01Ⓜ︎\x01Ⓝ︎\x01Ⓞ︎\x01Ⓟ︎\x01Ⓠ︎\x01Ⓡ︎\x01Ⓢ︎\x01Ⓣ︎\x01Ⓤ︎\x01Ⓥ︎\x01Ⓦ︎\x01Ⓧ︎\x01Ⓨ︎\x01Ⓩ︎\x01Ⓐ︎\x01Ⓑ︎\x01Ⓒ︎\x01Ⓓ︎\x01Ⓔ︎\x01Ⓕ︎\x01Ⓖ︎\x01Ⓗ︎\x01Ⓘ︎\x01Ⓙ︎\x01Ⓚ︎\x01Ⓛ︎\x01Ⓜ︎\x01Ⓝ︎\x01Ⓞ︎\x01Ⓟ︎\x01Ⓠ︎\x01Ⓡ︎\x01Ⓢ︎\x01Ⓣ︎\x01Ⓤ︎\x01Ⓥ︎\x01Ⓦ︎\x01Ⓧ︎\x01Ⓨ︎\x01Ⓩ︎\x01⓪\x01①\x01②\x01③\x01④\x01⑤\x01⑥\x01⑦\x01⑧\x01⑨',
    'dark_circle': '🅐︎\x01🅑︎\x01🅒︎\x01🅓︎\x01🅔︎\x01🅕︎\x01🅖︎\x01🅗︎\x01🅘︎\x01🅙︎\x01🅚︎\x01🅛︎\x01🅜︎\x01🅝︎\x01🅞︎\x01🅟︎\x01🅠︎\x01🅡︎\x01🅢︎\x01🅣︎\x01🅤︎\x01🅥︎\x01🅦︎\x01🅧︎\x01🅨︎\x01🅩︎\x01🅐︎\x01🅑︎\x01🅒︎\x01🅓︎\x01🅔︎\x01🅕︎\x01🅖︎\x01🅗︎\x01🅘︎\x01🅙︎\x01🅚︎\x01🅛︎\x01🅜︎\x01🅝︎\x01🅞︎\x01🅟︎\x01🅠︎\x01🅡︎\x01🅢︎\x01🅣︎\x01🅤︎\x01🅥︎\x01🅦︎\x01🅧︎\x01🅨︎\x01🅩\x01⓿\x01➊\x01➋\x01➌\x01➍\x01➎\x01➏\x01➐\x01➑\x01➒',
    'gothic': '𝔞\x01𝔟\x01𝔠\x01𝔡\x01𝔢\x01𝔣\x01𝔤\x01𝔥\x01𝔦\x01𝔧\x01𝔨\x01𝔩\x01𝔪\x01𝔫\x01𝔬\x01𝔭\x01𝔮\x01𝔯\x01𝔰\x01𝔱\x01𝔲\x01𝔳\x01𝔴\x01𝔵\x01𝔶\x01𝔷\x01𝔄\x01𝔅\x01ℭ\x01𝔇\x01𝔈\x01𝔉\x01𝔊\x01ℌ\x01ℑ\x01𝔍\x01𝔎\x01𝔏\x01𝔐\x01𝔑\x01𝔒\x01𝔓\x01𝔔\x01ℜ\x01𝔖\x01𝔗\x01𝔘\x01𝔙\x01𝔚\x01𝔛\x01𝔜\x01ℨ',
    'bold_gothic': '𝖆\x01𝖇\x01𝖈\x01𝖉\x01𝖊\x01𝖋\x01𝖌\x01𝖍\x01𝖎\x01𝖏\x01𝖐\x01𝖑\x01𝖒\x01𝖓\x01𝖔\x01𝖕\x01𝖖\x01𝖗\x01𝖘\x01𝖙\x01𝖚\x01𝖛\x01𝖜\x01𝖝\x01𝖞\x01𝖟\x01𝕬\x01𝕭\x01𝕮\x01𝕺\x01𝕰\x01𝕱\x01𝕲\x01𝕳\x01𝕴\x01𝕵\x01𝕶\x01𝕷\x01𝕸\x01𝕹\x01𝕺\x01𝕻\x01𝕼\x01𝕽\x01𝕾\x01𝕿\x01𝖀\x01𝖁\x01𝖂\x01𝖃\x01𝖄\x01𝖅',
    'cloud': 'a͜͡\x01b͜͡\x01c͜͡\x01d͜͡\x01e͜͡\x01f͜͡\x01g͜͡\x01h͜͡\x01i͜͡\x01j͜͡\x01k͜͡\x01l͜͡\x01m͜͡\x01n͜͡\x01o͜͡\x01p͜͡\x01q͜͡\x01r͜͡\x01s͜͡\x01t͜͡\x01u͜͡\x01v͜͡\x01w͜͡\x01x͜͡\x01y͜͡\x01z͜͡\x01A͜͡\x01B͜͡\x01C͜͡\x01D͜͡\x01E͜͡\x01F͜͡\x01G͜͡\x01H͜͡\x01I͜͡\x01J͜͡\x01K͜͡\x01L͜͡\x01M͜͡\x01N͜͡\x01O͜͡\x01P͜͡\x01Q͜͡\x01R͜͡\x01S͜͡\x01T͜͡\x01U͜͡\x01V͜͡\x01W͜͡\x01X͜͡\x01Y͜͡\x01Z͜͡',
    'happy': 'ă̈\x01b̆̈\x01c̆̈\x01d̆̈\x01ĕ̈\x01f̆̈\x01ğ̈\x01h̆̈\x01ĭ̈\x01j̆̈\x01k̆̈\x01l̆̈\x01m̆̈\x01n̆̈\x01ŏ̈\x01p̆̈\x01q̆̈\x01r̆̈\x01s̆̈\x01t̆̈\x01ŭ̈\x01v̆̈\x01w̆̈\x01x̆̈\x01y̆̈\x01z̆̈\x01Ă̈\x01B̆̈\x01C̆̈\x01D̆̈\x01Ĕ̈\x01F̆̈\x01Ğ̈\x01H̆̈\x01Ĭ̈\x01J̆̈\x01K̆̈\x01L̆̈\x01M̆̈\x01N̆̈\x01Ŏ̈\x01P̆̈\x01Q̆̈\x01R̆̈\x01S̆̈\x01T̆̈\x01Ŭ̈\x01V̆̈\x01W̆̈\x01X̆̈\x01Y̆̈\x01Z̆̈',
    'sad': 'ȃ̈\x01b̑̈\x01c̑̈\x01d̑̈\x01ȇ̈\x01f̑̈\x01g̑̈\x01h̑̈\x01ȋ̈\x01j̑̈\x01k̑̈\x01l̑̈\x01m̑̈\x01n̑̈\x01ȏ̈\x01p̑̈\x01q̑̈\x01ȓ̈\x01s̑̈\x01t̑̈\x01ȗ̈\x01v̑̈\x01w̑̈\x01x̑̈\x01y̑̈\x01z̑̈\x01Ȃ̈\x01B̑̈\x01C̑̈\x01D̑̈\x01Ȇ̈\x01F̑̈\x01G̑̈\x01H̑̈\x01Ȋ̈\x01J̑̈\x01K̑̈\x01L̑̈\x01M̑̈\x01N̑̈\x01Ȏ̈\x01P̑̈\x01Q̑̈\x01Ȓ̈\x01S̑̈\x01T̑̈\x01Ȗ̈\x01V̑̈\x01W̑̈\x01X̑̈\x01Y̑̈\x01Z̑̈',
    'special': '🇦\u200a\x01🇧\u200a\x01🇨\u200a\x01🇩\u200a\x01🇪\u200a\x01🇫\u200a\x01🇬\u200a\x01🇭\u200a\x01🇮\u200a\x01🇯\u200a\x01🇰\u200a\x01🇱\u200a\x01🇲\u200a\x01🇳\u200a\x01🇴\u200a\x01🇵\u200a\x01🇶\u200a\x01🇷\u200a\x01🇸\u200a\x01🇹\u200a\x01🇺\u200a\x01🇻\u200a\x01🇼\u200a\x01🇽\u200a\x01🇾\u200a\x01🇿\u200a\x01🇦\u200a\x01🇧\u200a\x01🇨\u200a\x01🇩\u200a\x01🇪\u200a\x01🇫\u200a\x01🇬\u200a\x01🇭\u200a\x01🇮\u200a\x01🇯\u200a\x01🇰\u200a\x01🇱\u200a\x01🇲\u200a\x01🇳\u200a\x01🇴\u200a\x01🇵\u200a\x01🇶\u200a\x01🇷\u200a\x01🇸\u200a\x01🇹\u200a\x01🇺\u200a\x01🇻\u200a\x01🇼\u200a\x01🇽\u200a\x01🇾\u200a\x01🇿\u200a',
    'square': '🄰\x01🄱\x01🄲\x01🄳\x01🄴\x01🄵\x01🄶\x01🄷\x01🄸\x01🄹\x01🄺\x01🄻\x01🄼\x01🄽\x01🄾\x01🄿\x01🅀\x01🅁\x01🅂\x01🅃\x01🅄\x01🅅\x01🅆\x01🅇\x01🅈\x01🅉\x01🄰\x01🄱\x01🄲\x01🄳\x01🄴\x01🄵\x01🄶\x01🄷\x01🄸\x01🄹\x01🄺\x01🄻\x01🄼\x01🄽\x01🄾\x01🄿\x01🅀\x01🅁\x01🅂\x01🅃\x01🅄\x01🅅\x01🅆\x01🅇\x01🅈\x01🅉',
    'dark_square': '🅰︎\x01🅱︎\x01🅲︎\x01🅳︎\x01🅴︎\x01🅵︎\x01🅶︎\x01🅷︎\x01🅸︎\x01🅹︎\x01🅺︎\x01🅻︎\x01🅼︎\x01🅽︎\x01🅾︎\x01🅿︎\x01🆀︎\x01🆁︎\x01🆂︎\x01🆃︎\x01🆄︎\x01🆅︎\x01🆆︎\x01🆇︎\x01🆈︎\x01🆉︎\x01🅰︎\x01🅱︎\x01🅲︎\x01🅳︎\x01🅴︎\x01🅵︎\x01🅶︎\x01🅷︎\x01🅸︎\x01🅹︎\x01🅺︎\x01🅻︎\x01🅼︎\x01🅽︎\x01🅾︎\x01🅿︎\x01🆀︎\x01🆁︎\x01🆂︎\x01🆃︎\x01🆄︎\x01🆅︎\x01🆆︎\x01🆇︎\x01🆈︎\x01🆉︎',
    'andalucia': 'ꪖ\x01᥇\x01ᥴ\x01ᦔ\x01ꫀ\x01ᠻ\x01ᧁ\x01ꫝ\x01𝓲\x01𝓳\x01𝘬\x01ꪶ\x01ꪑ\x01ꪀ\x01ꪮ\x01ρ\x01𝘲\x01𝘳\x01𝘴\x01𝓽\x01ꪊ\x01ꪜ\x01᭙\x01᥊\x01ꪗ\x01ɀ\x01ꪖ\x01᥇\x01ᥴ\x01ᦔ\x01ꫀ\x01ᠻ\x01ᧁ\x01ꫝ\x01𝓲\x01𝓳\x01𝘬\x01ꪶ\x01ꪑ\x01ꪀ\x01ꪮ\x01ρ\x01𝘲\x01𝘳\x01𝘴\x01𝓽\x01ꪊ\x01ꪜ\x01᭙\x01᥊\x01ꪗ\x01ɀ',
    'manga': '卂\x01乃\x01匚\x01ᗪ\x01乇\x01千\x01ᘜ\x01卄\x01|\x01ﾌ\x01Ҝ\x01ㄥ\x01爪\x01几\x01ㄖ\x01卩\x01Ҩ\x01尺\x01丂\x01ㄒ\x01ㄩ\x01ᐯ\x01山\x01乂\x01ㄚ\x01乙\x01卂\x01乃\x01匚\x01ᗪ\x01乇\x01千\x01ᘜ\x01卄\x01|\x01ﾌ\x01Ҝ\x01ㄥ\x01爪\x01几\x01ㄖ\x01卩\x01Ҩ\x01尺\x01丂\x01ㄒ\x01ㄩ\x01ᐯ\x01山\x01乂\x01ㄚ\x01乙',
    'stinky': 'a̾\x01b̾\x01c̾\x01d̾\x01e̾\x01f̾\x01g̾\x01h̾\x01i̾\x01j̾\x01k̾\x01l̾\x01m̾\x01n̾\x01o̾\x01p̾\x01q̾\x01r̾\x01s̾\x01t̾\x01u̾\x01v̾\x01w̾\x01x̾\x01y̾\x01z̾\x01A̾\x01B̾\x01C̾\x01D̾\x01E̾\x01F̾\x01G̾\x01H̾\x01I̾\x01J̾\x01K̾\x01L̾\x01M̾\x01N̾\x01O̾\x01P̾\x01Q̾\x01R̾\x01S̾\x01T̾\x01U̾\x01V̾\x01W̾\x01X̾\x01Y̾\x01Z̾',
    'bubbles': 'ḁͦ\x01b̥ͦ\x01c̥ͦ\x01d̥ͦ\x01e̥ͦ\x01f̥ͦ\x01g̥ͦ\x01h̥ͦ\x01i̥ͦ\x01j̥ͦ\x01k̥ͦ\x01l̥ͦ\x01m̥ͦ\x01n̥ͦ\x01o̥ͦ\x01p̥ͦ\x01q̥ͦ\x01r̥ͦ\x01s̥ͦ\x01t̥ͦ\x01u̥ͦ\x01v̥ͦ\x01w̥ͦ\x01x̥ͦ\x01y̥ͦ\x01z̥ͦ\x01Ḁͦ\x01B̥ͦ\x01C̥ͦ\x01D̥ͦ\x01E̥ͦ\x01F̥ͦ\x01G̥ͦ\x01H̥ͦ\x01I̥ͦ\x01J̥ͦ\x01K̥ͦ\x01L̥ͦ\x01M̥ͦ\x01N̥ͦ\x01O̥ͦ\x01P̥ͦ\x01Q̥ͦ\x01R̥ͦ\x01S̥ͦ\x01T̥ͦ\x01U̥ͦ\x01V̥ͦ\x01W̥ͦ\x01X̥ͦ\x01Y̥ͦ\x01Z̥ͦ',
    'underline': 'a͟\x01b͟\x01c͟\x01d͟\x01e͟\x01f͟\x01g͟\x01h͟\x01i͟\x01j͟\x01k͟\x01l͟\x01m͟\x01n͟\x01o͟\x01p͟\x01q͟\x01r͟\x01s͟\x01t͟\x01u͟\x01v͟\x01w͟\x01x͟\x01y͟\x01z͟\x01A͟\x01B͟\x01C͟\x01D͟\x01E͟\x01F͟\x01G͟\x01H͟\x01I͟\x01J͟\x01K͟\x01L͟\x01M͟\x01N͟\x01O͟\x01P͟\x01Q͟\x01R͟\x01S͟\x01T͟\x01U͟\x01V͟\x01W͟\x01X͟\x01Y͟\x01Z͟',
    'ladybug': 'ꍏ\x01ꌃ\x01ꏳ\x01ꀷ\x01ꏂ\x01ꎇ\x01ꁅ\x01ꀍ\x01ꀤ\x01꒻\x01ꀘ\x01꒒\x01ꎭ\x01ꈤ\x01ꂦ\x01ᖘ\x01ꆰ\x01ꋪ\x01ꌚ\x01꓄\x01ꀎ\x01꒦\x01ꅐ\x01ꉧ\x01ꌩ\x01ꁴ\x01ꍏ\x01ꌃ\x01ꏳ\x01ꀷ\x01ꏂ\x01ꎇ\x01ꁅ\x01ꀍ\x01ꀤ\x01꒻\x01ꀘ\x01꒒\x01ꎭ\x01ꈤ\x01ꂦ\x01ᖘ\x01ꆰ\x01ꋪ\x01ꌚ\x01꓄\x01ꀎ\x01꒦\x01ꅐ\x01ꉧ\x01ꌩ\x01ꁴ',
    'rays': 'a҉\x01b҉\x01c҉\x01d҉\x01e҉\x01f҉\x01g҉\x01h҉\x01i҉\x01j҉\x01k҉\x01l҉\x01m҉\x01n҉\x01o҉\x01p҉\x01q҉\x01r҉\x01s҉\x01t҉\x01u҉\x01v҉\x01w҉\x01x҉\x01y҉\x01z҉\x01A҉\x01B҉\x01C҉\x01D҉\x01E҉\x01F҉\x01G҉\x01H҉\x01I҉\x01J҉\x01K҉\x01L҉\x01M҉\x01N҉\x01O҉\x01P҉\x01Q҉\x01R҉\x01S҉\x01T҉\x01U҉\x01V҉\x01W҉\x01X҉\x01Y҉\x01Z҉',
    'birds': 'a҈\x01b҈\x01c҈\x01d҈\x01e҈\x01f҈\x01g҈\x01h҈\x01i҈\x01j҈\x01k҈\x01l҈\x01m҈\x01n҈\x01o҈\x01p҈\x01q҈\x01r҈\x01s҈\x01t҈\x01u҈\x01v҈\x01w҈\x01x҈\x01y҈\x01z҈\x01A҈\x01B҈\x01C҈\x01D҈\x01E҈\x01F҈\x01G҈\x01H҈\x01I҈\x01J҈\x01K҈\x01L҈\x01M҈\x01N҈\x01O҈\x01P҈\x01Q҈\x01R҈\x01S҈\x01T҈\x01U҈\x01V҈\x01W҈\x01X҈\x01Y҈\x01Z҈',
    'slash': 'a̸\x01b̸\x01c̸\x01d̸\x01e̸\x01f̸\x01g̸\x01h̸\x01i̸\x01j̸\x01k̸\x01l̸\x01m̸\x01n̸\x01o̸\x01p̸\x01q̸\x01r̸\x01s̸\x01t̸\x01u̸\x01v̸\x01w̸\x01x̸\x01y̸\x01z̸\x01A̸\x01B̸\x01C̸\x01D̸\x01E̸\x01F̸\x01G̸\x01H̸\x01I̸\x01J̸\x01K̸\x01L̸\x01M̸\x01N̸\x01O̸\x01P̸\x01Q̸\x01R̸\x01S̸\x01T̸\x01U̸\x01V̸\x01W̸\x01X̸\x01Y̸\x01Z̸',
    'stop': 'a⃠\x01b⃠\x01c⃠\x01d⃠\x01e⃠\x01f⃠\x01g⃠\x01h⃠\x01i⃠\x01j⃠\x01k⃠\x01l⃠\x01m⃠\x01n⃠\x01o⃠\x01p⃠\x01q⃠\x01r⃠\x01s⃠\x01t⃠\x01u⃠\x01v⃠\x01w⃠\x01x⃠\x01y⃠\x01z⃠\x01A⃠\x01B⃠\x01C⃠\x01D⃠\x01E⃠\x01F⃠\x01G⃠\x01H⃠\x01I⃠\x01J⃠\x01K⃠\x01L⃠\x01M⃠\x01N⃠\x01O⃠\x01P⃠\x01Q⃠\x01R⃠\x01S⃠\x01T⃠\x01U⃠\x01V⃠\x01W⃠\x01X⃠\x01Y⃠\x01Z⃠',
    'skyline': 'a̺͆\x01b̺͆\x01c̺͆\x01d̺͆\x01e̺͆\x01f̺͆\x01g̺͆\x01h̺͆\x01i̺͆\x01j̺͆\x01k̺͆\x01l̺͆\x01m̺͆\x01n̺͆\x01o̺͆\x01p̺͆\x01q̺͆\x01r̺͆\x01s̺͆\x01t̺͆\x01u̺͆\x01v̺͆\x01w̺͆\x01x̺͆\x01y̺͆\x01z̺͆\x01A̺͆\x01B̺͆\x01C̺͆\x01D̺͆\x01E̺͆\x01F̺͆\x01G̺͆\x01H̺͆\x01I̺͆\x01J̺͆\x01K̺͆\x01L̺͆\x01M̺͆\x01N̺͆\x01O̺͆\x01P̺͆\x01Q̺͆\x01R̺͆\x01S̺͆\x01T̺͆\x01U̺͆\x01V̺͆\x01W̺͆\x01X̺͆\x01Y̺͆\x01Z̺͆',
    'arrows': 'a͎\x01b͎\x01c͎\x01d͎\x01e͎\x01f͎\x01g͎\x01h͎\x01i͎\x01j͎\x01k͎\x01l͎\x01m͎\x01n͎\x01o͎\x01p͎\x01q͎\x01r͎\x01s͎\x01t͎\x01u͎\x01v͎\x01w͎\x01x͎\x01y͎\x01z͎\x01A͎\x01B͎\x01C͎\x01D͎\x01E͎\x01F͎\x01G͎\x01H͎\x01I͎\x01J͎\x01K͎\x01L͎\x01M͎\x01N͎\x01O͎\x01P͎\x01Q͎\x01R͎\x01S͎\x01T͎\x01U͎\x01V͎\x01W͎\x01X͎\x01Y͎\x01Z͎',
    'rvnes': 'ል\x01ጌ\x01ር\x01ዕ\x01ቿ\x01ቻ\x01ኗ\x01ዘ\x01ጎ\x01ጋ\x01ጕ\x01ረ\x01ጠ\x01ክ\x01ዐ\x01የ\x01ዒ\x01ዪ\x01ነ\x01ፕ\x01ሁ\x01ሀ\x01ሠ\x01ሸ\x01ሃ\x01ጊ\x01ል\x01ጌ\x01ር\x01ዕ\x01ቿ\x01ቻ\x01ኗ\x01ዘ\x01ጎ\x01ጋ\x01ጕ\x01ረ\x01ጠ\x01ክ\x01ዐ\x01የ\x01ዒ\x01ዪ\x01ነ\x01ፕ\x01ሁ\x01ሀ\x01ሠ\x01ሸ\x01ሃ\x01ጊ',
    'strike': 'a̶\x01b̶\x01c̶\x01d̶\x01e̶\x01f̶\x01g̶\x01h̶\x01i̶\x01j̶\x01k̶\x01l̶\x01m̶\x01n̶\x01o̶\x01p̶\x01q̶\x01r̶\x01s̶\x01t̶\x01u̶\x01v̶\x01w̶\x01x̶\x01y̶\x01z̶\x01A̶\x01B̶\x01C̶\x01D̶\x01E̶\x01F̶\x01G̶\x01H̶\x01I̶\x01J̶\x01K̶\x01L̶\x01M̶\x01N̶\x01O̶\x01P̶\x01Q̶\x01R̶\x01S̶\x01T̶\x01U̶\x01V̶\x01W̶\x01X̶\x01Y̶\x01Z̶',
    'frozen': 'a༙\x01b༙\x01c༙\x01d༙\x01e༙\x01f༙\x01g༙\x01h༙\x01i༙\x01j༙\x01k༙\x01l༙\x01m༙\x01n༙\x01o༙\x01p༙\x01q༙\x01r༙\x01s༙\x01t༙\x01u༙\x01v༙\x01w༙\x01x༙\x01y༙\x01z༙\x01A༙\x01B༙\x01C༙\x01D༙\x01E༙\x01F༙\x01G༙\x01H༙\x01I༙\x01J༙\x01K༙\x01L༙\x01M༙\x01N༙\x01O༙\x01P༙\x01Q༙\x01R༙\x01S༙\x01T༙\x01U༙\x01V༙\x01W༙\x01X༙\x01Y༙\x01Z༙',
}

class Fonts:
    @staticmethod
    def _apply(text, val_str):
        keys = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        values = val_str.split('\x01')
        if len(values) == 62:
            keys += '0123456789'
        for i, j in zip(keys, values):
            text = text.replace(i, j)
        return text

    def typewriter(text): return Fonts._apply(text, FONTS_DATA['typewriter'])
    def outline(text): return Fonts._apply(text, FONTS_DATA['outline'])
    def serief(text): return Fonts._apply(text, FONTS_DATA['serief'])
    def bold_cool(text): return Fonts._apply(text, FONTS_DATA['bold_cool'])
    def cool(text): return Fonts._apply(text, FONTS_DATA['cool'])
    def randi(text): return Fonts._apply(text, FONTS_DATA['randi'])
    def randava(text): return Fonts._apply(text, FONTS_DATA['randava'])
    def smallcap(text): return Fonts._apply(text, FONTS_DATA['smallcap'])
    def script(text): return Fonts._apply(text, FONTS_DATA['script'])
    def bold_script(text): return Fonts._apply(text, FONTS_DATA['bold_script'])
    def tiny(text): return Fonts._apply(text, FONTS_DATA['tiny'])
    def comic(text): return Fonts._apply(text, FONTS_DATA['comic'])
    def san(text): return Fonts._apply(text, FONTS_DATA['san'])
    def slant_san(text): return Fonts._apply(text, FONTS_DATA['slant_san'])
    def slant(text): return Fonts._apply(text, FONTS_DATA['slant'])
    def sim(text): return Fonts._apply(text, FONTS_DATA['sim'])
    def circles(text): return Fonts._apply(text, FONTS_DATA['circles'])
    def dark_circle(text): return Fonts._apply(text, FONTS_DATA['dark_circle'])
    def gothic(text): return Fonts._apply(text, FONTS_DATA['gothic'])
    def bold_gothic(text): return Fonts._apply(text, FONTS_DATA['bold_gothic'])
    def cloud(text): return Fonts._apply(text, FONTS_DATA['cloud'])
    def happy(text): return Fonts._apply(text, FONTS_DATA['happy'])
    def sad(text): return Fonts._apply(text, FONTS_DATA['sad'])
    def special(text): return Fonts._apply(text, FONTS_DATA['special'])
    def square(text): return Fonts._apply(text, FONTS_DATA['square'])
    def dark_square(text): return Fonts._apply(text, FONTS_DATA['dark_square'])
    def andalucia(text): return Fonts._apply(text, FONTS_DATA['andalucia'])
    def manga(text): return Fonts._apply(text, FONTS_DATA['manga'])
    def stinky(text): return Fonts._apply(text, FONTS_DATA['stinky'])
    def bubbles(text): return Fonts._apply(text, FONTS_DATA['bubbles'])
    def underline(text): return Fonts._apply(text, FONTS_DATA['underline'])
    def ladybug(text): return Fonts._apply(text, FONTS_DATA['ladybug'])
    def rays(text): return Fonts._apply(text, FONTS_DATA['rays'])
    def birds(text): return Fonts._apply(text, FONTS_DATA['birds'])
    def slash(text): return Fonts._apply(text, FONTS_DATA['slash'])
    def stop(text): return Fonts._apply(text, FONTS_DATA['stop'])
    def skyline(text): return Fonts._apply(text, FONTS_DATA['skyline'])
    def arrows(text): return Fonts._apply(text, FONTS_DATA['arrows'])
    def rvnes(text): return Fonts._apply(text, FONTS_DATA['rvnes'])
    def strike(text): return Fonts._apply(text, FONTS_DATA['strike'])
    def frozen(text): return Fonts._apply(text, FONTS_DATA['frozen'])


@app.on_message(filters.command(["font", "fonts", "f"], prefixes=["/", "!", ".", ""]))
async def style_buttons(c, m, cb=False):
    buttons = [
        [
            InlineKeyboardButton("𝚃𝚢𝚙𝚎𝚠𝚛𝚒𝚝𝚎𝚛", callback_data="style+typewriter"),
            InlineKeyboardButton("𝕆𝕦𝕥𝕝𝕚𝕟𝕖", callback_data="style+outline"),
            InlineKeyboardButton("𝐒𝐞𝐫𝐢𝐟", callback_data="style+serif"),
        ],
        [
            InlineKeyboardButton("𝑺𝒆𝒓𝒊𝒇", callback_data="style+bold_cool"),
            InlineKeyboardButton("𝑆𝑒𝑟𝑖𝑓", callback_data="style+cool"),
            InlineKeyboardButton("ʀᴧηᴅɪ", callback_data="style+randi"),
        ],
        [
            InlineKeyboardButton("ʀᴧηᴅᴧѵᴧ", callback_data="style+randava"),
            InlineKeyboardButton("Sᴍᴀʟʟ Cᴀᴘs", callback_data="style+small_cap"),
            InlineKeyboardButton("𝓈𝒸𝓇𝒾𝓅𝓉", callback_data="style+script"),
        ],
        [
            InlineKeyboardButton("𝓼𝓬𝓻𝓲𝓹𝓽", callback_data="style+script_bolt"),
            InlineKeyboardButton("ᵗⁱⁿʸ", callback_data="style+tiny"),
            InlineKeyboardButton("ᑕOᗰIᑕ", callback_data="style+comic"),
        ],
        [
            InlineKeyboardButton("𝗦𝗮𝗻𝘀", callback_data="style+sans"),
            InlineKeyboardButton("𝙎𝙖𝙣𝙨", callback_data="style+slant_sans"),
            InlineKeyboardButton("𝘚𝘢𝘯𝘴", callback_data="style+slant"),
        ],
        [
            InlineKeyboardButton("𝖲𝖺𝗇𝗌", callback_data="style+sim"),
            InlineKeyboardButton("Ⓒ︎Ⓘ︎Ⓡ︎Ⓒ︎Ⓛ︎Ⓔ︎Ⓢ︎", callback_data="style+circles"),
            InlineKeyboardButton("🅒︎🅘︎🅡︎🅒︎🅛︎🅔︎🅢︎", callback_data="style+circle_dark"),
        ],
        [
            InlineKeyboardButton("𝔊𝔬𝔱𝔥𝔦𝔠", callback_data="style+gothic"),
            InlineKeyboardButton("𝕲𝖔𝖙𝖍𝖎𝖈", callback_data="style+gothic_bolt"),
            InlineKeyboardButton("C͜͡l͜͡o͜͡u͜͡d͜͡s͜͡", callback_data="style+cloud"),
        ],
        [
            InlineKeyboardButton("H̆̈ă̈p̆̈p̆̈y̆̈", callback_data="style+happy"),
            InlineKeyboardButton("S̑̈ȃ̈d̑̈", callback_data="style+sad"),
        ],
        [InlineKeyboardButton("ɴᴇxᴛ ➻", callback_data="nxt")],
    ]
    if not cb:
        _args = (m.text or "").split(None, 1)
        if len(_args) < 2 or not _args[1].strip():
            return await m.reply_text(
                "❌ <b>Usage:</b> <code>/font your text here</code>"
            )
        # Kurigram 2.2+ removed the `quote` kwarg; bound reply_text() already
        # sets reply_parameters so the message is sent as a reply by default.
        await m.reply_text(
            text=_args[1],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        await m.answer()
        await m.message.edit_reply_markup(InlineKeyboardMarkup(buttons))


@app.on_callback_query(filters.regex("^nxt"))
async def nxt(c, m):
    if m.data == "nxt":
        buttons = [
            [
                InlineKeyboardButton("🇸 🇵 🇪 🇨 🇮 🇦 🇱 ", callback_data="style+special"),
                InlineKeyboardButton("🅂🅀🅄🄰🅁🄴🅂", callback_data="style+squares"),
                InlineKeyboardButton("🆂︎🆀︎🆄︎🅰︎🆁︎🅴︎🆂︎", callback_data="style+squares_bold"),
            ],
            [
                InlineKeyboardButton("ꪖꪀᦔꪖꪶꪊᥴ𝓲ꪖ", callback_data="style+andalucia"),
                InlineKeyboardButton("爪卂几ᘜ卂", callback_data="style+manga"),
                InlineKeyboardButton("S̾t̾i̾n̾k̾y̾", callback_data="style+stinky"),
            ],
            [
                InlineKeyboardButton("B̥ͦu̥ͦb̥ͦb̥ͦl̥ͦe̥ͦs̥ͦ", callback_data="style+bubbles"),
                InlineKeyboardButton("U͟n͟d͟e͟r͟l͟i͟n͟e͟", callback_data="style+underline"),
                InlineKeyboardButton("꒒ꍏꀷꌩꌃꀎꁅ", callback_data="style+ladybug"),
            ],
            [
                InlineKeyboardButton("R҉a҉y҉s҉", callback_data="style+rays"),
                InlineKeyboardButton("B҈i҈r҈d҈s҈", callback_data="style+birds"),
                InlineKeyboardButton("S̸l̸a̸s̸h̸", callback_data="style+slash"),
            ],
            [
                InlineKeyboardButton("s⃠t⃠o⃠p⃠", callback_data="style+stop"),
                InlineKeyboardButton("S̺͆k̺͆y̺͆l̺͆i̺͆n̺͆e̺͆", callback_data="style+skyline"),
                InlineKeyboardButton("A͎r͎r͎o͎w͎s͎", callback_data="style+arrows"),
            ],
            [
                InlineKeyboardButton("ዪሀክቿነ", callback_data="style+qvnes"),
                InlineKeyboardButton("S̶t̶r̶i̶k̶e̶", callback_data="style+strike"),
                InlineKeyboardButton("F༙r༙o༙z༙e༙n༙", callback_data="style+frozen"),
            ],
            [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="nxt+0")],
        ]
        await m.answer()
        await m.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
    else:
        await style_buttons(c, m, cb=True)


STYLE_MAP = {
    "typewriter": "typewriter",
    "outline": "outline",
    "serif": "serief",
    "bold_cool": "bold_cool",
    "cool": "cool",
    "randi": "randi",
    "randava": "randava",
    "small_cap": "smallcap",
    "script": "script",
    "script_bolt": "bold_script",
    "tiny": "tiny",
    "comic": "comic",
    "sans": "san",
    "slant_sans": "slant_san",
    "slant": "slant",
    "sim": "sim",
    "circles": "circles",
    "circle_dark": "dark_circle",
    "gothic": "gothic",
    "gothic_bolt": "bold_gothic",
    "cloud": "cloud",
    "happy": "happy",
    "sad": "sad",
    "special": "special",
    "squares": "square",
    "squares_bold": "dark_square",
    "andalucia": "andalucia",
    "manga": "manga",
    "stinky": "stinky",
    "bubbles": "bubbles",
    "underline": "underline",
    "ladybug": "ladybug",
    "rays": "rays",
    "birds": "birds",
    "slash": "slash",
    "stop": "stop",
    "skyline": "skyline",
    "arrows": "arrows",
    "qvnes": "rvnes",
    "strike": "strike",
    "frozen": "frozen"
}

@app.on_callback_query(filters.regex("^style"))
async def style(c, m):
    await m.answer()
    _, style_name = m.data.split("+")
    method_name = STYLE_MAP.get(style_name)
    if method_name:
        cls = getattr(Fonts, method_name)
        new_text = cls(m.message.reply_to_message.text.split(None, 1)[1])
        try:
            await m.message.edit_text(f"`{new_text}`")
        except BaseException:
            pass
