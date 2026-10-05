# صوتك يهمنا — Your Voice Matters

A feedback web app for the St. Athanasios youth service. Members can send
suggestions, raise concerns, ask for contact or prayer, point out someone who
needs follow-up, share encouragement, or volunteer to help. They pick one at a
time and can send another right after.

The UI is in Arabic (Egyptian dialect), right-to-left, and built to work well
on phones.

## How it works

The app runs as a **Google Apps Script web app**.
[`apps-script/Index.html`](apps-script/Index.html) is an
[HTML Service template](https://developers.google.com/apps-script/guides/html/templates):
the server fills in the template variables, serves the page, and receives the
submission through `google.script.run`.

The public link is <https://stathanasiosyouth.github.io/your-voice-matters/>.
GitHub Pages serves the root [`index.html`](index.html), which only shows the
Apps Script web app full-screen in an iframe. The app can't run on Pages
directly: template tags and `google.script.run` only work when Apps Script
serves the page.

| File                     | Where it runs                               |
| ------------------------ | ------------------------------------------- |
| `apps-script/Index.html` | Apps Script (the actual app)                |
| `index.html`             | GitHub Pages (iframe wrapper around `/exec`) |
| `res/`                   | Images, loaded from GitHub by both          |

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

The cards work like radio buttons: picking one shows only that type's form.
The sender's name and phone are asked for only when the chosen item needs them
(a named message, a contact request, etc.), and they're kept between
submissions. Phone numbers are validated as Egyptian mobiles
(`01[0125]XXXXXXXX` or `+201…`), and Arabic or Persian digits are converted
automatically.

### After sending

A popup confirms the submission with an animation that fits its type, then
asks whether there's something else to send. **Yes** clears the form and
scrolls back to the choices; **No** shows the thank-you screen.

| Type          | Mood   | Animation                          |
| ------------- | ------ | ---------------------------------- |
| `suggestion`  | Joyful | Confetti cannons from both corners |
| `positive`    | Joyful | Burst of hearts                    |
| `participate` | Joyful | Burst of gold stars                |
| `contact`     | Light  | Ripple rings and floating gold dots |
| `followup`    | Warm   | Hearts rising slowly               |
| `prayer`      | Warm   | Flickering candle and rising embers |
| `complaint`   | Calm   | Soft blue lights drifting up       |

The animations are skipped when the device asks for reduced motion.

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

`items` always holds exactly one item, since one type is sent at a time. It stays
an array so the server code doesn't need to change. Unused fields are sent as
empty strings. The page ignores the return value. Throw an `Error` to show its
message to the user.

Minimal `doGet` example:

```js
function doGet() {
  const template = HtmlService.createTemplateFromFile('Index');
  template.pageTitle = 'صوتك يهمنا';
  template.serviceName = '…';

  return template
    .evaluate()
    .setTitle('صوتك يهمنا')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    // required, or the GitHub Pages iframe shows a blank/refused page
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
```

## Deploying

1. Open (or create) the Apps Script project at <https://script.google.com>.
2. Add an HTML file named `Index` and paste in the contents of
   `apps-script/Index.html`.
3. Add the server code (`doGet` and `submitMessages`).
4. **Deploy → New deployment → Web app**. Set *Execute as* to **Me** and
   *Who has access* to **Anyone**, or visitors on GitHub Pages will be asked to
   sign in.
5. Put the `/exec` URL in the root `index.html` iframe `src`.

To update the app later, use **Deploy → Manage deployments → Edit → New
version**. That keeps the same `/exec` URL, so `index.html` doesn't change.

Optional: use [clasp](https://github.com/google/clasp) to push from this repo
instead of copy-pasting (`clasp clone <scriptId>`, then `clasp push`).
