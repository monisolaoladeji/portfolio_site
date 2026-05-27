# Portfolio Site (Admin Editable)

This portfolio uses Flask with MongoDB for persistence (on Vercel) and SQLite for local development.

## Features

- Admin login with persistent authentication
- Permanent profile photo upload (to Cloudinary)
- Add/update/delete projects from admin dashboard
- Permanent project screenshot uploads (to Cloudinary)
- Public portfolio page for visitors
- All portfolio content stored in MongoDB (survives Vercel restarts)

## First-time setup (write once)

1. Open terminal in this folder.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run app once:
   - `python app.py`
4. A `local_config.json` file will be created automatically.

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
   - Public site: `http://127.0.0.1:5000/` (local port may vary)
   - Admin login: `http://127.0.0.1:5000/admin/login`

## Deployment to Vercel (IMPORTANT)

**You MUST set `MONGODB_URI` as an environment variable in Vercel for portfolio content to persist:**

1. Get a MongoDB URI:
   - Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
   - Create a free cluster
   - Get the connection string (looks like: `mongodb+srv://username:password@cluster.mongodb.net/portfolio_site?retryWrites=true&w=majority`)

2. Set Vercel environment variables:
   - `MONGODB_URI` - your MongoDB connection string
   - `PORTFOLIO_CLOUDINARY_CLOUD_NAME` - your Cloudinary name
   - `PORTFOLIO_CLOUDINARY_API_KEY` - your Cloudinary key
   - `PORTFOLIO_CLOUDINARY_API_SECRET` - your Cloudinary secret

3. Deploy to Vercel
   - Without `MONGODB_URI`, your portfolio will reset on every restart!
   - With `MONGODB_URI`, all your projects, screenshots, and contact info will survive Vercel restarts

## Local development

- Uses SQLite by default (local file: `portfolio.db`)
- Automatically falls back to SQLite if `MONGODB_URI` is not set
- MongoDB connection is optional locally but highly recommended for testing production behavior

## Cloudinary setup

To move existing local uploads into Cloudinary, run:
- `python migrate_uploads_to_cloudinary.py`

Then all new uploads will automatically use Cloudinary.

## Email notifications for visitor messages

Edit `local_config.json`:

- `"SMTP_ENABLED": true`
- `"SMTP_HOST": "smtp.gmail.com"` (or your provider)
- `"SMTP_PORT": 587`
- `"SMTP_USERNAME": "you@example.com"`
- `"SMTP_PASSWORD": "your-app-password"`
- `"SMTP_USE_TLS": true`
- `"NOTIFY_TO_EMAIL": "you@example.com"`
- `"NOTIFY_FROM_EMAIL": "you@example.com"`

Then restart: `python app.py`

## Troubleshooting

**Q: My portfolio is still empty after deployment**
- A: Make sure `MONGODB_URI` is set in Vercel. Without it, the app uses a temporary database that resets.

**Q: Images are not showing**
- A: Make sure Cloudinary credentials are set: `PORTFOLIO_CLOUDINARY_CLOUD_NAME`, `PORTFOLIO_CLOUDINARY_API_KEY`, `PORTFOLIO_CLOUDINARY_API_SECRET`

**Q: Can I use this locally without MongoDB?**
- A: Yes! The app falls back to SQLite automatically when `MONGODB_URI` is not set. But for production, MongoDB is required for persistence.
