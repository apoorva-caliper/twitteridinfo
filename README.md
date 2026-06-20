# Twitter / X Post Scraper

Fetch company posting patterns from X (Twitter): last 50 posts per profile with likes, reposts, comments, and content.

Built on [twikit](https://github.com/d60/twikit) via the maintained [unclecode/twikit](https://github.com/unclecode/twikit) fork (required because upstream broke in March 2026).

---

## What you need

- Python 3.10+
- A free X/Twitter account (any account you can log into at [x.com](https://x.com))
- Company profile URLs (e.g. `https://x.com/OpenAI`)

No X Developer API key is required.

---

## 1. Install

```bash
git clone <this-repo-url>
cd calipersocial

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 2. Set up authentication (`.env`)

X blocks unauthenticated scraping. You authenticate once by copying two browser cookies into a `.env` file.

### Step A — Copy the example file

```bash
cp .env.example .env
```

### Step B — Get your cookies from the browser

1. Open [https://x.com](https://x.com) and **log in** with your account.
2. Open **Developer Tools**:
   - **Chrome / Edge / Brave:** press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
   - **Firefox:** press `F12` → **Storage** tab
   - **Safari:** enable Developer menu in Settings → Advanced, then **Develop → Show Web Inspector**
3. Go to the **Cookies** section:
   - **Chrome / Edge:** **Application** tab → left sidebar → **Cookies** → `https://x.com`
   - **Firefox:** **Storage** → **Cookies** → `https://x.com`
   - **Safari:** **Storage** → **Cookies** → `x.com`
4. Find these two cookies and copy each **Value** column:

| Cookie name | What it is |
|-------------|------------|
| `auth_token` | Your logged-in session token |
| `ct0` | CSRF security token (required on every request) |

> **Tip:** In the cookie list, use the filter/search box and type `auth` or `ct0` to find them quickly.

### Step C — Paste into `.env`

Open `.env` and fill in the values (no quotes needed):

```env
TWITTER_AUTH_TOKEN=paste_your_auth_token_here
TWITTER_CT0=paste_your_ct0_here
```

Save the file. **Do not commit `.env`** — it is like a password for your X account.

### When cookies expire

If you get auth errors later, repeat Step B and update `.env` with fresh values. Cookies usually last weeks to months.

---

## 3. Run — fetch company profiles (main use case)

### Interactive mode (recommended for new users)

Run the script with no arguments. Paste profile URLs **one at a time**, then press **Enter on an empty line** when done:

```bash
python fetch_accounts.py
```

Example session:

```
Profile URL or handle: https://x.com/EpochAIResearch
  Added @EpochAIResearch
Profile URL or handle: https://x.com/arizeai
  Added @arizeai
Profile URL or handle:

Profiles to fetch: @EpochAIResearch, @arizeai
Fetching @EpochAIResearch (last 50 posts)...
  Got 50 posts
...
```

Accepted input formats:

- `https://x.com/CompanyName`
- `https://twitter.com/CompanyName`
- `@CompanyName`
- `CompanyName`

### Pass URLs directly on the command line

```bash
python fetch_accounts.py --url https://x.com/EpochAIResearch https://x.com/ValsAI
```

### Change how many posts to fetch (default: 50)

```bash
python fetch_accounts.py --url https://x.com/OpenAI --limit 100
```

### Filter by minimum likes

Only save posts that meet a like threshold:

```bash
python fetch_accounts.py --url https://x.com/ValsAI --min-likes 100
```

This scans recent posts and keeps up to `--limit` posts that have **at least** 100 likes. If a company posts mostly low-engagement content, increase `--limit` or lower the threshold.

In interactive mode, you'll also be asked:

```
Minimum likes required (default 0, 0 = no filter): 50
```

Set a default in `.env` so you don't have to type it every time:

```env
MIN_LIKES=100
```

### Use a file instead of typing in the terminal

Add one profile URL or handle per line to `accounts.txt`, then:

```bash
python fetch_accounts.py --file accounts.txt
```

---

## 4. Output files

After a run you get:

| File | Contents |
|------|----------|
| `accounts_posts.csv` | Spreadsheet — open in Excel/Numbers/Google Sheets |
| `accounts_posts.json` | Full post data + account summaries |
| `accounts_patterns.json` | Posting cadence, weekday/hour patterns, average engagement |

Each post includes: `content`, `likes`, `reposts`, `comments`, `views`, `created_at`, `url`, and `profile_url`.

---

## 5. Fetch individual tweets (optional)

Use `fetch_posts.py` when you have **specific post URLs**, not company profiles.

### Interactive

```bash
python fetch_posts.py
```

Paste tweet URLs one by one:

```
Tweet URL or ID: https://x.com/elonmusk/status/1519480761749016577
  Added tweet 1519480761749016577
Tweet URL or ID:
```

### Command line

```bash
python fetch_posts.py --url https://x.com/user/status/1234567890123456789 --min-likes 1000
```

Only posts meeting the like threshold are saved to the output files.

### How to find a tweet ID

Every post URL looks like:

```
https://x.com/username/status/1234567890123456789
                              ^^^^^^^^^^^^^^^^^^^
                              this number is the tweet ID
```

Output saves to `posts_output.csv` and `posts_output.json`.

---

## 6. Troubleshooting

| Problem | Fix |
|---------|-----|
| `Authentication required` | Create `.env` with `TWITTER_AUTH_TOKEN` and `TWITTER_CT0` (see Section 2) |
| `401` / `403` errors | Cookies expired — copy fresh `auth_token` and `ct0` from the browser |
| `That looks like a tweet URL, not a profile` | You pasted a post URL into `fetch_accounts.py`. Use the company **profile** URL (`https://x.com/CompanyName`) or switch to `fetch_posts.py` for individual posts |
| `Couldn't get KEY_BYTE indices` | Reinstall dependencies: `pip install -r requirements.txt` (uses the patched twikit fork) |
| Empty or partial results | Account may be private, suspended, or have fewer than 50 posts |

---

## Project structure

```
calipersocial/
├── .env.example          # Template — copy to .env
├── accounts.txt          # Optional: saved profile list
├── fetch_accounts.py     # Main script — company profiles
├── fetch_posts.py        # Optional — individual tweet URLs/IDs
├── twitter_utils.py      # Shared auth and parsing helpers
├── requirements.txt
└── README.md
```

---

## Quick reference

```bash
# Activate environment (do this every new terminal session)
source venv/bin/activate

# Fetch companies — paste URLs interactively
python fetch_accounts.py

# Fetch companies — pass URLs directly, min 50 likes
python fetch_accounts.py --url https://x.com/SomeCompany --min-likes 50

# Fetch specific tweets, min 1000 likes
python fetch_posts.py --url https://x.com/user/status/1234567890 --min-likes 1000
```
