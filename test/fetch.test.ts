// The PIB fetcher's parsing, on a page shaped like the real one. A release
// page lists every language of the release except its own, so the page's own
// language has to come out of its text. Importing this must not fetch: the
// scraper's work sits behind `import.meta.main`.
import { describe, expect, test } from 'bun:test'
import { groupOf, linkReport, pageLang, parseRelease, releaseUrl, settled } from '../fetch'

const page = (title: string, links: string) =>
  `<div class="innner-page-main-about-us-content-right-part">` +
  `<div id="MinistryName" class="x">Ministry of Textiles</div>` +
  `<h1 id="Titleh2">${title}</h1>` +
  `<div id="PrDateTime" class="x">Posted On: 04 OCT 2026 7:01PM by PIB Delhi</div>` +
  `<p>Cotton Corporation of India</p>` +
  `<span id="ReleaseId">(Release ID: 2318919)</span><span id="lblViews">Visitor Counter : 11</span>` +
  `</div><div id="P_CategoryManagement"></div>` +
  `<div class="ReleaseLang">Read this release in: ${links}</div>`

const link = (prid: string, label: string) => `<a href='https://pib.gov.in/PressReleasePage.aspx?PRID=${prid}' target="_blank"> ${label} </a>`

describe('PIB release parsing', () => {
  test('an English page, which lists only its translations', () => {
    const r = parseRelease('2318919', page('Cotton reforms', link('2318933', 'हिन्दी')), 'en')
    expect(r.lang).toBe('en')
    expect(r.title).toBe('Cotton reforms')
    expect(r.body).toBe('Cotton Corporation of India')
    expect(r.translations).toEqual({ hi: '2318933' })
  })

  test('a translation page, named by its own script', () => {
    const r = parseRelease('2318933', page('कपास सुधार', link('2318919', 'English')))
    expect(r.lang).toBe('hi')
    expect(r.translations).toEqual({ en: '2318919' })
  })

  test('decodes the entities PIB writes into its paragraphs', () => {
    const html = page('T', link('2318919', 'हिन्दी')).replace(
      '<p>Cotton Corporation of India</p>',
      '<p>as part of &lsquo;Reform Utsav 2026&rsquo; &mdash; &amp;lsquo;twice&amp;rsquo; &nbsp;&#8377;4,000</p>',
    )
    expect(parseRelease('2318919', html, 'en').body).toBe('as part of \u2018Reform Utsav 2026\u2019 \u2014 \u2018twice\u2019 \u20b94,000')
  })

  test('the feed names the language where the script cannot', () => {
    expect(pageLang('कपास सुधार', 'mr')).toBe('mr')
    expect(pageLang('कपास सुधार', 'hi')).toBe('hi')
    expect(pageLang('Cotton reforms', 'en')).toBe('en')
  })
})

describe('cache freshness', () => {
  // A release gains its translations in the days after it is posted: a page
  // cached on day one would keep an empty language block for good.
  const html = page('Cotton reforms', '')
  test('a page read within a week of its release is not settled', () => {
    expect(settled(html, new Date('2026-10-06T12:00:00Z'))).toBe(false)
  })
  test('a week on, it is settled and the cache is trusted', () => {
    expect(settled(html, new Date('2026-10-12T12:00:00Z'))).toBe(true)
  })
  test('a page with no readable date is trusted, not refetched forever', () => {
    expect(settled('<div>no date</div>', new Date())).toBe(true)
  })
})


describe('languages that share a script with another', () => {
  test('a Devanagari page from the Konkani feed is Konkani, not Hindi', () => {
    expect(pageLang('पणजे येथ कार्यक्रम', 'gom')).toBe('gom')
  })
  test('a Latin-script page from the Mizo, Khasi or Tenyidei feed is not English', () => {
    expect(pageLang('Mizoram-ah hun pawimawh', 'lus')).toBe('lus')
    expect(pageLang('Ka jingiaseng', 'kha')).toBe('kha')
    expect(pageLang('Kohima ki', 'njm')).toBe('njm')
  })
  test('Manipuri in Bengali script stays Manipuri', () => {
    expect(pageLang('মণিপুরগী', 'mni')).toBe('mni')
  })
  test('the danda is shared punctuation, not a sign of Hindi', () => {
    // Chandigarh, November 2025: 117 Punjabi pairs were labelled Hindi, because "।" sits in the
    // Devanagari block and the first script found won.
    expect(pageLang('ਪ੍ਰਧਾਨ ਮੰਤਰੀ 27 ਨਵੰਬਰ ਨੂੰ ਸਕਾਈਰੂਟ ਦੇ ਇਨਫਿਨਿਟੀ ਕੈਂਪਸ ਦਾ ਉਦਘਾਟਨ ਕਰਨਗੇ।', 'pa')).toBe('pa')
    expect(pageLang('ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਉਦਘਾਟਨ ਕਰਨਗੇ।', '')).toBe('pa')
    expect(pageLang('প্রধানমন্ত্রী আজ উদ্বোধন করবেন।', '')).toBe('bn')
  })

  test('the script with the most letters wins, so an English acronym in an Indic headline does not', () => {
    expect(pageLang('ISRO ने आज नया उपग्रह छोड़ा', '')).toBe('hi')
  })

  test('with no hint, Latin is English', () => {
    expect(pageLang('Union Minister visits Kohima', '')).toBe('en')
  })
})

describe('entities PIB writes', () => {
  test('zero-width joiners come back as the characters, not as entity text', () => {
    // 2195987, Hindi: प्रसन्&zwj;नता came through undecoded.
    const r = parseRelease('1', page('प्रसन्&zwj;नता और नि&zwnj;यम', ''), 'hi')
    expect(r.title).toBe('प्रसन्‍नता और नि‌यम')
  })
})

describe('the event layout (IFFI releases)', () => {
  // 2190187: the container's class name first appears in a style sheet, the page
  // has no dateline, and every release ends with the same festival paragraph.
  // 489 of 3,481 pilot releases came out with CSS before the prose and the
  // counter after it.
  const event =
    `<style>.innner-page-main-about-us-content-right-part { padding: 35px; }</style>` +
    `<div class="innner-page-main-about-us-content-right-part">` +
    `<div class="text-center event-heading-background"><h1 id="Titleh2">इफ्फी पोर्टल</h1>` +
    `<h3 id="Subtitleh3"><span id="ltrSubtitle"></span></h3></div>` +
    `<div class='pt20'></div><p>माध्यमांसाठी शेवटची संधी.</p>` +
    `<div class="text-center"><div id="FooterEventText"><p>Great films resonate through passionate voices.</p></div>` +
    `<p class="mb-1"><strong>रिलीज़ आईडी:</strong><span id="ReleaseIdEvent">2190187</span> | ` +
    `<strong>Visitor Counter:</strong><span id="lblViewsEvent">51</span></p>` +
    `<div class="ReleaseLang">इस विज्ञप्ति को इन भाषाओं में पढ़ें: ${link('2190116', 'English')}</div></div></div>` +
    `<div id="P_CategoryManagement"></div>`

  test('the body is the prose alone: no style sheet, no festival paragraph, no counter', () => {
    const r = parseRelease('2190187', event, 'mr')
    expect(r.title).toBe('इफ्फी पोर्टल')
    expect(r.body).toBe('माध्यमांसाठी शेवटची संधी.')
    expect(r.translations).toEqual({ en: '2190116' })
  })
})

describe('pages that are not a release', () => {
  test("PIB's error page, which can be cached with status 200, gives an empty release", () => {
    // 2189162: "The Page you have requested is not available at present."
    const r = parseRelease('2189162', '<html><head><title>Untitled Page</title><script>!function(e){}</script></head><body>The Page you have requested is not available at present.</body></html>')
    expect(r.title).toBe('')
    expect(r.body).toBe('')
  })
  test('a footer pasted into the prose is dropped with its line', () => {
    // 2196509: an editor pasted another release's id and visitor count into the text.
    const html = page('T', '').replace('<p>Cotton Corporation of India</p>', '<p>Cotton Corporation of India</p><p>रिलीज़ आईडी: 2195544 | Visitor Counter: 173</p>')
    expect(parseRelease('1', html, 'en').body).toBe('Cotton Corporation of India')
  })
})

describe('office language labels', () => {
  test('an office variant names its language', () => {
    const r = parseRelease('1', page('T', link('2', 'Bengali-TR') + link('3', 'Telugu_Vw')), 'en')
    expect(r.translations).toEqual({ bn: '2', te: '3' })
  })
  test('but never replaces the national translation, in either order', () => {
    const a = parseRelease('1', page('T', link('10', 'हिन्दी') + link('11', 'Hindi_Cg')), 'en')
    const b = parseRelease('1', page('T', link('11', 'Hindi_Cg') + link('10', 'हिन्दी')), 'en')
    expect(a.translations).toEqual({ hi: '10' })
    expect(b.translations).toEqual({ hi: '10' })
  })
})

describe('release groups', () => {
  const release = (prid: string, lang: string, body: string) =>
    ({ prid, lang, title: body ? 'T' : '', subtitle: '', ministry: 'M', date: 'D', body, translations: {} })
  test('every side carries its own PRID, and a blank translation is left out', () => {
    // 2189023 (Marathi) is a 56 KB page with an empty title and body. The PRIDs
    // let a document pair be aligned once: Delhi's English with its Marathi and
    // Mumbai's Marathi with its English are the same pair, and the pilot held
    // 118,616 duplicate sentence pairs before this.
    expect(groupOf(release('1', 'en', 'Text'), [release('2', 'mr', ''), release('3', 'hi', 'पाठ')])).toEqual({
      prid: '1', date: 'D', ministry: 'M',
      byLang: { en: { prid: '1', title: 'T', body: 'Text' }, hi: { prid: '3', title: 'T', body: 'पाठ' } },
    })
  })
  test('a group whose own release is blank is no group', () => {
    expect(groupOf(release('1', 'mr', ''), [release('2', 'en', 'Text')])).toBeNull()
  })
})

describe('the release URL', () => {
  test('names an office and a language, so PIB answers without a redirect', () => {
    // The bare URL answers 302 to this form: a quarter of each page's time. Any
    // reg and lang give the same release; only the page's own menu changes.
    expect(releaseUrl('2186691')).toBe('https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2186691&reg=3&lang=1')
  })
})

describe('what the corpus must not carry', () => {
  // Measured on the 10,265 pilot pages: 1,669 embed tweets, most of them left in
  // English on translated pages; 93 give institutional email addresses and 68
  // official phone numbers. Nothing personal was found, but none of it is text
  // a translation corpus needs, and a tweet is third-party material.
  const withBody = (body: string) => page('T', '').replace('<p>Cotton Corporation of India</p>', body)

  test('an embedded tweet goes, signature and all', () => {
    const html = withBody(
      '<p>The Prime Minister wrote:</p><blockquote class="twitter-tweet"><p lang="en" dir="ltr">Greetings to Chhattisgarh.</p>' +
        '&mdash; Narendra Modi (@narendramodi) <a href="https://twitter.com/x">November 1, 2025</a></blockquote><p>He added more.</p>',
    )
    expect(parseRelease('1', html, 'en').body).toBe('The Prime Minister wrote:\nHe added more.')
  })

  test('whatever else the tweet tag carries', () => {
    // 1,798 pilot tweets are "twitter-tweet tw-align-center", 180 add align="center".
    const html = withBody(
      '<p>Before.</p><blockquote class="twitter-tweet tw-align-center"><p>One.</p></blockquote>' +
        '<blockquote class="twitter-tweet"  align="center" ><p>Two.</p></blockquote><p>After.</p>',
    )
    expect(parseRelease('1', html, 'en').body).toBe('Before.\nAfter.')
  })

  test('a tweet whose class an editor dropped, known by its link, while a plain quotation stays', () => {
    // 2189026: the Malayalam page translates the tweet in a paragraph above and keeps the tweet itself in English.
    const html = withBody(
      '<p>ആന്റെ ശ്രീയുടെ വിയോഗം.</p><blockquote><p dir="ltr">The passing of Ande Sri leaves a deep void.</p>' +
        '&mdash; Narendra Modi (@narendramodi) <a href="https://twitter.com/narendramodi/status/1987810558687543436">November 10, 2025</a></blockquote>' +
        '<blockquote><p>A line from the Constitution.</p></blockquote>',
    )
    expect(parseRelease('1', html, 'ml').body).toBe('ആന്റെ ശ്രീയുടെ വിയോഗം.\nA line from the Constitution.')
  })

  test('an email address becomes a placeholder, written plainly or obfuscated', () => {
    const body = parseRelease('1', withBody('<p>Write to iffi.mediadesk@pib.gov.in or ddg1[dot]nad[at]mospi[dot]gov[dot]in today.</p>'), 'en').body
    expect(body).toBe('Write to <email> or <email> today.')
  })

  test('a phone number becomes a placeholder, in any script', () => {
    const body = parseRelease('1', withBody('<p>Call 7827170170, 1800-180-1503, (080-4611 0007) or 011-23385271، ०११-२३३८५२७१.</p>'), 'en').body
    expect(body).toBe('Call <phone>, <phone>, (<phone>) or <phone>، <phone>.')
  })

  test('the forms an independent audit of the November 2025 data found after the first rules', () => {
    const cases: Array<[string, string]> = [
      ['TRAI नो ટેલિફોન નંબર + 91-11-20907757 પર', 'TRAI नो ટેલિફોન નંબર <phone> પર'],
      ['اورفون نمبر -23000761 +91-40 پر رابطہ', 'اورفون نمبر <phone> پر رابطہ'],
      ['call 1-800-891-4416 today', 'call <phone> today'],
      ['ईमेल: adv.ca@trai. gov.in या', 'ईमेल: <email> या'],
      ['at email rmsdoek.kl.@indiapost.gov.in titled', 'at email <email> titled'],
      ['ای میل ( csm-upsc [at] nic [dot] in ) یا', 'ای میل ( <email> ) یا'],
      ['अभिप्राय jsseeds-agri [at]gov[dot]in या', 'अभिप्राय <email> या'],
      ['write to a@b.gov.in. Next sentence.', 'write to <email>. Next sentence.'],
      // Found by audit.py in the packaged month: a mobile split 5-5, and one in Bengali digits.
      ['ਸੰਪਰਕ 74283-21144 ਤੇ', 'ਸੰਪਰਕ <phone> ਤੇ'],
      ['হোয়াটসঅ্যাপ নম্বর ৭২১৭৭৩৫৩৭২ চালু', 'হোয়াটসঅ্যাপ নম্বর <phone> চালু'],
      // regional/mni, blocked by audit.py: digits of another script inside an address, dots or two
      // separators between a number's groups. The spaced address loses its [at] part, which is the
      // part that makes it one.
      ['ইমেল: advfea২@trai.gov.in সেক্রেতরী', 'ইমেল: <email> সেক্রেতরী'],
      ['ক্বেরীসিংগীদমক technicalquery.covid১৯[at]gov[dot]in দা', 'ক্বেরীসিংগীদমক <email> দা'],
      ['ক্বেরীশিংগীদমক্তা technicalquery.covid ১৯ [at]gov[dot]in দা', 'ক্বেরীশিংগীদমক্তা technicalquery.covid <email> দা'],
      ['Phone: + 91.40.3086 6419', 'Phone: <phone>'],
      ['may be contacted at Tel. No. +91-11- 20907774.', 'may be contacted at Tel. No. <phone>.'],
      // May 2021, blocked by audit.py: a mixed-case domain, and +91 in Bengali digits on a Manipuri page.
      ['কম্পনিশী contact@INDRAwater.com या ईमेलवर', 'কম্পনিশী <email> या ईमेलवर'],
      ['দা. রাজেন্দ্র বদৱে, +৯১৯৬১৯১৯৭৬৩৯, নেস', 'দা. রাজেন্দ্র বদৱে, <phone>, নেস'],
      ['হেল্পলাইন ১৮০০-১৮০-১৫০৩ নম্বরে', 'হেল্পলাইন <phone> নম্বরে'],
      // August 2023, blocked by audit.py: Kannada and Telugu join a case ending to the number.
      ['ದೂರವಾಣಿ ಸಂಖ್ಯೆ +91-11-23210481ರಲ್ಲಿ ಸಂಪರ್ಕಿಸಿ', 'ದೂರವಾಣಿ ಸಂಖ್ಯೆ <phone>ರಲ್ಲಿ ಸಂಪರ್ಕಿಸಿ'],
      ['టెలిఫోన్ నంబర్ +91-11-23237922లో సంప్రదించవచ్చు', 'టెలిఫోన్ నంబర్ <phone>లో సంప్రదించవచ్చు'],
      ['ಸಹಾಯವಾಣಿ 7827170170ಗೆ ಕರೆ ಮಾಡಿ', 'ಸಹಾಯವಾಣಿ <phone>ಗೆ ಕರೆ ಮಾಡಿ'],
      // July 2019, blocked by audit.py: an address in capitals.
      ['through e-mail on “BSNLGOGREENATD@GMAIL.COM’ at the earliest', 'through e-mail on “<email>’ at the earliest'],
      ['WRITE TO INFO@PIB.GOV.IN. THE OFFICE', 'WRITE TO <email>. THE OFFICE'],
    ]
    for (const [text, want] of cases) expect(parseRelease('1', withBody(`<p>${text}</p>`), 'en').body).toBe(want)
  })

  test('with the country code, which drops the trunk 0', () => {
    // Shillong, November 2025: "No. +91-33-22361401" passed the first rule.
    const body = parseRelease('1', withBody('<p>No. +91-33-22361401 or +91 11 2338 9338 or +91-9876543210.</p>'), 'en').body
    expect(body).toBe('No. <phone> or <phone> or <phone>.')
  })

  test('but a number inside an identifier, an amount or a date is left alone', () => {
    const text = 'App id6739700695, report MPR011020257F52BD, Rs 1,00,00,000 crore, 29.10.2025, PRID 2195987, year 2047.'
    expect(parseRelease('1', withBody(`<p>${text}</p>`), 'en').body).toBe(text)
  })
})

describe('the link report', () => {
  // In November 2018 Chandigarh's Punjabi and Bhubaneswar's Odia releases linked
  // no translation at all, so this method found nothing there. A run says so.
  const rel = (lang: string, translations: Record<string, string>) =>
    ({ prid: '1', lang, title: 'T', subtitle: '', ministry: '', date: '', body: 'B', translations })
  test('a regional run counts the releases that link their English', () => {
    expect(linkReport([rel('pa', {}), rel('pa', {}), rel('pa', { en: '9' })])).toBe('1 of 3 releases link an English translation')
  })
  test('an English run counts the releases that link any translation', () => {
    expect(linkReport([rel('en', { hi: '2' }), rel('en', {})])).toBe('1 of 2 releases link a translation')
  })
})
