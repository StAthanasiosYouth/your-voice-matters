# صوتك يهمنا — Your Voice Matters

A feedback web app for the St. Athanasios youth service. Members can send
suggestions, raise concerns, ask for contact or prayer, point out someone who
needs follow-up, share encouragement, or volunteer to help — several at once,
in one submission.

The UI is in Arabic (Egyptian dialect), right-to-left, and built to work well
on phones.

## How it works

The app runs as a **Google Apps Script web app**. `Index.html` is an
[HTML Service template](https://developers.google.com/apps-script/guides/html/templates):
the server fills in the template variables, serves the page, and receives the
submission through `google.script.run`.

### Feedback types

| Type          | Card                             | Collects                                                        |
| ------------- | -------------------------------- | --------------------------------------------------------------- |
| `suggestion`  | عندي رأي أو اقتراح               | Message; anonymous or named                                     |
| `complaint`   | في حاجة مضايقاني                 | Message; whether they want to be contacted                      |
| `contact`     | محتاج حد من الخدمة يتواصل معايا   | Contact method (WhatsApp, call, visit, any); optional note      |
| `followup`    | في شخص محتاج نفتقده              | Person's name, phone, area, details; whether they know          |
| `prayer`      | محتاج صلاة أو مشورة               | Message; whether they want to talk to someone                   |
| `positive`    | حابب أقول حاجة حلوة              | Message; anonymous or named                                     |
| `participate` | حابب أشارك أو أساعد              | Area (organization, activities, media, acting, music, …); note  |

The sender's name and phone are asked for **once**, and only when a selected
item needs them (a named message, a contact request, etc.). Phone numbers are
validated as Egyptian mobiles (`01[0125]XXXXXXXX` or `+201…`), and Arabic or
Persian digits are converted automatically.

## Server-side contract

The server-side `.gs` code is not in this repository yet. It must provide:

**Template variables** set before `evaluate()`:

| Variable      | Used for                           |
| ------------- | ---------------------------------- |
| `pageTitle`   | Browser tab title                  |
| `serviceName` | Service name under the header title |

Images live in [`res/`](res) and are loaded straight from this repository
through `raw.githubusercontent.com`:

| File             | Used for                            |
| ---------------- | ----------------------------------- |
| `res/logo.png`   | Logo on the intro screen and header |
| `res/banner.png` | Banner image at the top of the page |

To change an image, replace the file and push to `main`.

**`submitMessages(payload)`**, called from the page with:

```js
{
  profile: { name, phone },
  items: [
    {
      type,              // one of the feedback types above
      message,
      identity,          // "anonymous" | "named"
      wantsContact,      // "yes" | "no"
      contactMethod,     // "whatsapp" | "call" | "visit" | "any"
      personName,
      personPhone,
      personArea,
      personDetails,
      personConsent,     // "yes" | "not-sure"
      participationArea
    }
  ]
}
```

Unused fields are sent as empty strings. On success, return an object with a
`count` property (number of items saved); the page uses it to choose its thank-you
message. Throw an `Error` to show its message to the user.

Minimal `doGet` example:

```js
function doGet() {
  const template = HtmlService.createTemplateFromFile('Index');
  template.pageTitle = 'صوتك يهمنا';
  template.serviceName = '…';

  return template
    .evaluate()
    .setTitle('صوتك يهمنا')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
```

## Deploying

1. Open (or create) the Apps Script project at <https://script.google.com>.
2. Add an HTML file named `Index` and paste in the contents of `Index.html`.
3. Add the server code (`doGet` and `submitMessages`).
4. **Deploy → New deployment → Web app**, then choose who can access it.

Optional: use [clasp](https://github.com/google/clasp) to push from this repo
instead of copy-pasting (`clasp clone <scriptId>`, then `clasp push`).
