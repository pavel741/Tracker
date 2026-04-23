# How to Deploy to Railway

Step-by-step guide to get the Visitation Tracker live on Railway's free tier.

---

## Prerequisites

- A [GitHub](https://github.com) account
- A [Railway](https://railway.app) account (sign up free with GitHub)

---

## Step 1: Push to GitHub

1. Create a new repository on GitHub (e.g. `visitation-tracker`)
2. Open a terminal in the `visitation-tracker` folder and run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/visitation-tracker.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

---

## Step 2: Create a Railway Project

1. Go to [railway.app](https://railway.app) and click **Start a New Project**
2. Select **Deploy from GitHub repo**
3. Find and select your `visitation-tracker` repository
4. Railway will detect the Python project automatically and begin building

---

## Step 3: Add a Persistent Volume

The SQLite database needs a persistent volume so your data survives redeploys.

1. In your Railway project, click on your service
2. Go to the **Volumes** tab (or click **+ New** and select **Volume**)
3. Set the **Mount Path** to: `/data`
4. Click **Add**

---

## Step 4: Set Environment Variables

1. In your service, go to the **Variables** tab
2. Add these two variables:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | A long random string (see below) |
| `RAILWAY_VOLUME_MOUNT_PATH` | `/data` |

To generate a secure `SECRET_KEY`, run this in any terminal:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the value.

---

## Step 5: Deploy

1. Railway auto-deploys when you push to GitHub, or click **Deploy** manually
2. Wait for the build to finish (usually 1-2 minutes)
3. Once deployed, Railway gives you a public URL like `https://visitation-tracker-production-xxxx.up.railway.app`

---

## Step 6: Verify

1. Open your Railway URL in a browser
2. You should see the **login page**
3. Click **Register** to create your account
4. Start logging visitation records

---

## Updating the App

Any time you push changes to GitHub, Railway automatically redeploys:

```bash
git add .
git commit -m "Update description"
git push
```

---

## Custom Domain (Optional)

1. In your Railway service, go to **Settings** > **Networking**
2. Click **Generate Domain** to get a free `*.up.railway.app` domain
3. Or click **Custom Domain** and follow the instructions to add your own (e.g. `tracker.yourdomain.com`)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| App crashes on deploy | Check the **Deploy Logs** tab in Railway for error messages |
| Data disappears after redeploy | Make sure the Volume is attached with mount path `/data` and `RAILWAY_VOLUME_MOUNT_PATH` is set to `/data` |
| "Internal Server Error" | Check that `SECRET_KEY` is set in environment variables |
| Can't reach the site | Go to **Settings** > **Networking** and click **Generate Domain** |
| Pip install fails | Check `requirements.txt` exists in the root of the repo |

---

## Architecture

```
Browser  -->  Railway (Free Tier)
                |
                v
           Gunicorn + Flask
                |
                v
           SQLite on Volume (/data/visitation.db)
```

All data stays on your Railway volume. No external database needed.
