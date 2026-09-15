# IG Following Review - Streamlit + Supabase

A private, mobile-friendly Streamlit app for reviewing an Instagram `following.json` export one profile at a time.

## What is stored

Supabase stores:
- Instagram username
- Instagram profile URL
- followed timestamp from the export
- your review status: `pending`, `keep`, `unfollowed`, or `later`
- last update time

Your Instagram password is never requested or stored. The app does not unfollow accounts automatically.

## 1. Create Supabase storage

1. Go to https://supabase.com and create a project.
2. Open **SQL Editor**.
3. Paste the contents of `schema.sql` and run it.
4. Go to **Project Settings -> API**.
5. Copy:
   - Project URL
   - Service role key

Keep the service role key private.

## 2. Put the app on GitHub

Create a GitHub repository and add:

- `app.py`
- `requirements.txt`
- `schema.sql`
- `.streamlit/config.toml`

Do **not** commit your Supabase service role key.

## 3. Deploy to Streamlit Community Cloud

1. Go to https://share.streamlit.io
2. Create a new app from your GitHub repository.
3. Set the main file to `app.py`.
4. In the app's **Settings -> Secrets**, add:

```toml
APP_PASSWORD = "choose-a-strong-password"
OWNER_ID = "my-instagram-review"
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_SERVICE_ROLE_KEY"
```

5. Reboot the app if Streamlit asks you to.

## 4. First use

1. Open the deployed Streamlit URL.
2. Enter your app password.
3. Upload your Instagram `following.json` once.
4. Click **Save to cloud storage**.

After the first import, the list is stored in Supabase. You do not need to upload the JSON every time.

## 5. Review from iPhone

For each account:

1. Tap **Open Instagram Profile**.
2. Inspect the profile in Instagram.
3. If you unfollow manually, return to the Streamlit app and tap **UNFOLLOWED**.
4. Otherwise choose **KEEP** or **LATER**.

Every choice is written to Supabase immediately, so you can close Safari and continue later, or switch between iPhone and Mac.

## Updating your following list later

Open the sidebar and upload a fresh `following.json`. Existing review statuses for usernames already in the database are preserved.

## Security notes

- Use a strong `APP_PASSWORD` because a Streamlit Community Cloud app may have a publicly reachable URL.
- Keep `SUPABASE_KEY` only in Streamlit Secrets.
- The service-role key stays on the Streamlit server; never expose it in browser JavaScript.
- The app only stores data from your own Instagram export plus your review decisions.
