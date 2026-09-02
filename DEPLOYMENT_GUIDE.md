# Deployment Guide - Cognitive Adaptive AI Tutor

This guide will help you deploy the **Backend (FastAPI)** to **Render** and the **Frontend (React + Vite)** to **Vercel**.

---

## 📋 Prerequisites

1. **GitHub Account**: [Mohammed-Shazi-Ul-Islam](https://github.com/Mohammed-Shazi-Ul-Islam)
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
4. **Supabase Account**: Your database and auth provider
5. **API Keys**: GROQ_API_KEY, GEMINI_API_KEY

---

## 🗂️ Project Structure

```
Capstone_project/
├── ui/                          # Frontend React application
│   ├── src/
│   ├── dist/                    # Build output (generated)
│   ├── package.json
│   ├── vite.config.js
│   └── .env                     # Frontend environment variables
├── core/                        # Backend Python modules
├── api_server.py                # Main FastAPI application
├── requirements.txt             # Python dependencies
├── Procfile                     # Render start command
├── runtime.txt                  # Python version for Render
├── render.yaml                  # Render configuration
├── vercel.json                  # Vercel configuration
└── .env                         # Backend environment variables

```

---

## 🚀 Part 1: Deploy Backend to Render

### Step 1: Push Code to GitHub

1. **Ensure all changes are committed to `develop` branch:**
   ```bash
   git add .
   git commit -m "Add deployment configuration files"
   git push origin develop
   ```

2. **Create and push the `deploy` branch:**
   ```bash
   git checkout -b deploy
   git push origin deploy
   ```

   The GitHub Action (`.github/workflows/sync-deploy.yml`) will automatically sync `deploy` branch whenever you push to `develop`.

### Step 2: Create Render Web Service

1. **Go to [Render Dashboard](https://dashboard.render.com/)**

2. **Click "New +" → "Web Service"**

3. **Connect your GitHub repository:**
   - Connect your GitHub account if not already connected
   - Select repository: `Mohammed-Shazi-Ul-Islam/Cognitive-Adaptive-AI-tutor`

4. **Configure the service:**
   - **Name**: `cognitive-ai-tutor-backend`
   - **Region**: Oregon (US West)
   - **Branch**: `deploy`
   - **Root Directory**: (leave empty - uses root)
   - **Runtime**: `Python 3`
   - **Build Command**: `chmod +x render-build.sh && ./render-build.sh`
   - **Start Command**: `uvicorn api_server:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120`
   - **Instance Type**: ⚠️ **Starter** (Free tier will likely run out of memory)

5. **Set Environment Variables** (click "Advanced" or go to Environment tab):
   ```
   GROQ_API_KEY=<your_groq_api_key>
   GEMINI_API_KEY=<your_gemini_api_key>
   SUPABASE_URL=<your_supabase_url>
   SUPABASE_SERVICE_KEY=<your_supabase_service_key>
   JWT_SECRET_KEY=<generate_a_random_secret_key>
   PYTHON_VERSION=3.11.0
   ```

   To generate JWT_SECRET_KEY, run:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

6. **Choose Free Plan** (or paid if needed)

7. **Click "Create Web Service"**

8. **Wait for deployment** (5-10 minutes for first deploy)

9. **Your backend URL** will be: `https://cognitive-ai-tutor-backend.onrender.com`

10. **Test the backend:**
    - Open: `https://cognitive-ai-tutor-backend.onrender.com/`
    - You should see: `{"status":"Cognitive Adaptive AI Tutor API running","version":"2.0.0"}`

### Important Notes for Render:
- ⚠️ **Free tier (512 MB) will likely fail with OOM** - This app needs 1-2 GB RAM due to ML dependencies
- **Recommended**: Use **Starter plan ($7/month, 2 GB RAM)** for reliable deployment
- **Free tier sleeps after 15 minutes of inactivity** - first request may take 30-60 seconds
- **Ensure `Procfile` and `runtime.txt` are in the root directory**
- **The `/data` directory may need persistent storage** - consider using Render Disks for production
- **If deployment fails with "Exited with status 137"** - See `RENDER_TROUBLESHOOTING.md`

---

## 🎨 Part 2: Deploy Frontend to Vercel

### Step 1: Update Frontend Environment Variables

1. **Create `ui/.env` file** (if it doesn't exist):
   ```env
   VITE_API_BASE_URL=https://cognitive-ai-tutor-backend.onrender.com
   VITE_SUPABASE_URL=<your_supabase_url>
   VITE_SUPABASE_ANON_KEY=<your_supabase_anon_key>
   ```

2. **Ensure API calls use the environment variable** - Check `ui/src/App.jsx` and other files use `import.meta.env.VITE_API_BASE_URL`

### Step 2: Deploy to Vercel

#### Option A: Using Vercel CLI (Recommended)

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel:**
   ```bash
   vercel login
   ```
   Enter your email: `mohammedshaziulislam7777@gmail.com`

3. **Navigate to project root:**
   ```bash
   cd "c:\Users\mohammed shazi\Desktop\SEM6\Capstone_project"
   ```

4. **Deploy:**
   ```bash
   vercel
   ```
   
   Answer the prompts:
   - Set up and deploy? **Y**
   - Which scope? Select your account
   - Link to existing project? **N**
   - Project name? `cognitive-ai-tutor-frontend` (or your choice)
   - In which directory is your code located? `./ui`
   - Want to override settings? **Y**
   - Build Command? `npm run build`
   - Output Directory? `dist`
   - Development Command? `npm run dev`

5. **Set environment variables in Vercel:**
   ```bash
   vercel env add VITE_API_BASE_URL
   ```
   Enter value: `https://cognitive-ai-tutor-backend.onrender.com`
   
   ```bash
   vercel env add VITE_SUPABASE_URL
   ```
   Enter your Supabase URL
   
   ```bash
   vercel env add VITE_SUPABASE_ANON_KEY
   ```
   Enter your Supabase Anon Key

6. **Deploy to production:**
   ```bash
   vercel --prod
   ```

#### Option B: Using Vercel Dashboard

1. **Go to [Vercel Dashboard](https://vercel.com/dashboard)**

2. **Click "Add New..." → "Project"**

3. **Import Git Repository:**
   - Connect GitHub account
   - Select: `Mohammed-Shazi-Ul-Islam/Cognitive-Adaptive-AI-tutor`

4. **Configure Project:**
   - **Framework Preset**: Vite
   - **Root Directory**: `ui`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`

5. **Add Environment Variables:**
   ```
   VITE_API_BASE_URL=https://cognitive-ai-tutor-backend.onrender.com
   VITE_SUPABASE_URL=<your_supabase_url>
   VITE_SUPABASE_ANON_KEY=<your_supabase_anon_key>
   ```

6. **Click "Deploy"**

7. **Your frontend URL** will be: `https://cognitive-ai-tutor-frontend.vercel.app` (or custom domain)

---

## 🔄 Automatic Deployment Workflow

Once set up, your deployment workflow will be:

1. **Make changes in your code**
2. **Commit and push to `develop` branch:**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin develop
   ```
3. **GitHub Action automatically syncs `develop` → `deploy`**
4. **Render automatically deploys backend** (from `deploy` branch)
5. **Vercel automatically deploys frontend** (from `develop` branch - configure in Vercel settings)

---

## 🔧 Update Backend CORS Settings

The backend (`api_server.py`) already includes your Vercel domains in CORS:

```python
allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://cognitive-adaptive-ai-tutor.vercel.app",
    "https://cognitive-adaptive-ai-tutor-git-deploy1-msui.vercel.app",
],
```

**Add your actual Vercel URL** after deployment:
1. Open `api_server.py`
2. Add your Vercel URL to the `allow_origins` list
3. Commit and push changes

---

## 🧪 Testing Your Deployment

### Test Backend:
```bash
curl https://cognitive-ai-tutor-backend.onrender.com/
```
Expected: `{"status":"Cognitive Adaptive AI Tutor API running","version":"2.0.0"}`

### Test Frontend:
1. Open your Vercel URL in browser
2. Try to login/signup
3. Check browser console for any CORS or API errors

---

## 📝 Environment Variables Checklist

### Backend (Render):
- ✅ GROQ_API_KEY
- ✅ GEMINI_API_KEY
- ✅ SUPABASE_URL
- ✅ SUPABASE_SERVICE_KEY
- ✅ JWT_SECRET_KEY
- ✅ PYTHON_VERSION

### Frontend (Vercel):
- ✅ VITE_API_BASE_URL
- ✅ VITE_SUPABASE_URL
- ✅ VITE_SUPABASE_ANON_KEY

---

## 🐛 Troubleshooting

### Backend Issues:

1. **"Application failed to start"**
   - Check Render logs for Python errors
   - Ensure all dependencies in `requirements.txt` are compatible
   - Verify `api_server:app` is the correct entry point

2. **"Module not found" errors**
   - Ensure `requirements.txt` has all dependencies
   - Check Python version matches (`runtime.txt`)

3. **CORS errors from frontend**
   - Add your Vercel URL to `allow_origins` in `api_server.py`
   - Redeploy backend

### Frontend Issues:

1. **"Failed to fetch" errors**
   - Verify `VITE_API_BASE_URL` is set correctly
   - Check backend is running (visit backend URL)
   - Check browser console for CORS errors

2. **Build fails**
   - Check Vercel build logs
   - Ensure `package.json` scripts are correct
   - Verify all dependencies are in `package.json`

3. **Environment variables not working**
   - In Vercel, environment variables must start with `VITE_`
   - Redeploy after adding environment variables

---

## 🎉 You're Done!

Your application is now deployed:
- **Backend**: https://cognitive-ai-tutor-backend.onrender.com
- **Frontend**: https://your-project.vercel.app

Any push to `develop` will automatically deploy through the `deploy` branch!

---

## 📧 Support

If you encounter issues:
1. Check Render logs: Dashboard → Your Service → Logs
2. Check Vercel logs: Dashboard → Your Project → Deployments → View Logs
3. Review GitHub Actions: Repository → Actions tab
