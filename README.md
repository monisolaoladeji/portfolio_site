# Portfolio Site (Admin Editable)

This portfolio now uses Flask + SQLite so only you (admin) can edit content.

## Features

- Admin login
- Permanent profile photo upload
- Add/update/delete projects from admin dashboard
- Permanent project screenshot uploads
- Public portfolio page for visitors

## First-time setup (write once)

1. Open terminal in this folder.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run app once:
   - `python app.py`
4. A `local_config.json` file will be created automatically.

> To save visitor messages permanently, set `MONGODB_URI` in Vercel or your local environment. Example env var name:
> `MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.eaer1cp.mongodb.net/portfolio_site?retryWrites=true&w=majority`
> 
> If `MONGODB_URI` is not set, the site will still use local SQLite as a fallback, but MongoDB is recommended for persistence on Vercel.

> Note: On Render/Vercel, local SQLite and uploaded files are not guaranteed to persist after the site sleeps or redeploys. For production, use a persistent database service or a platform-provided persistent disk, and set `PORTFOLIO_DB_PATH` to that path if available.
5. Open `local_config.json` and set your own values:
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
   - `SECRET_KEY`
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
6. Restart app:
   - `python app.py`
7. Open:
   - Public site: `http://127.0.0.1:5050/`
   - Admin login: `http://127.0.0.1:5050/admin/login`

## Important

- Visitors can only view content.
- Only users with admin credentials can change content.
- Uploaded images are saved in `static/uploads/`.
- Optional: env vars still work and override `local_config.json` when set.
- To move existing local uploads into Cloudinary, run:
  - `python migrate_uploads_to_cloudinary.py`

> For Vercel/Render, set these env vars instead of committing credentials:
> `PORTFOLIO_CLOUDINARY_CLOUD_NAME`, `PORTFOLIO_CLOUDINARY_API_KEY`, `PORTFOLIO_CLOUDINARY_API_SECRET`

## Email notifications for visitor messages

Edit `local_config.json` once:

- `"SMTP_ENABLED": true`
- `"SMTP_HOST": "smtp.gmail.com"` (or your provider)
- `"SMTP_PORT": 587`
- `"SMTP_USERNAME": "you@example.com"`
- `"SMTP_PASSWORD": "your-app-password"`
- `"SMTP_USE_TLS": true`
- `"NOTIFY_TO_EMAIL": "you@example.com"`
- `"NOTIFY_FROM_EMAIL": "you@example.com"`

Then restart:

- `python app.py`

Now each new visitor message is saved in dashboard and also sent to your email.
