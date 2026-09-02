# Quick Deploy Commands

## 🚀 Step-by-Step Deployment

### 1️⃣ Push to GitHub
```bash
# Ensure you're in the project directory
cd "c:\Users\mohammed shazi\Desktop\SEM6\Capstone_project"

# Add all deployment files
git add .
git commit -m "Add deployment configuration"

# Push to develop branch
git push origin develop

# Create and push deploy branch
git checkout -b deploy
git push origin deploy

# Go back to develop
git checkout develop
```

### 2️⃣ Deploy Backend to Render
1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Connect GitHub: `Mohammed-Shazi-Ul-Islam/Cognitive-Adaptive-AI-tutor`
4. Configure:
   - **Name**: `cognitive-ai-tutor-backend`
   - **Branch**: `deploy`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api_server:app --host 0.0.0.0 --port $PORT --workers 1`
5. Add Environment Variables (see DEPLOYMENT_GUIDE.md)
6. Click "Create Web Service"
7. Copy your backend URL (e.g., `https://cognitive-ai-tutor-backend.onrender.com`)

### 3️⃣ Deploy Frontend to Vercel

#### Using Vercel CLI:
```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login
# Enter: mohammedshaziulislam7777@gmail.com

# Deploy
cd "c:\Users\mohammed shazi\Desktop\SEM6\Capstone_project"
vercel

# Follow prompts:
# - Directory: ./ui
# - Build Command: npm run build
# - Output Directory: dist

# Add environment variables
vercel env add VITE_API_BASE_URL
# Enter your Render backend URL

vercel env add VITE_SUPABASE_URL
# Enter your Supabase URL

vercel env add VITE_SUPABASE_ANON_KEY
# Enter your Supabase anon key

# Deploy to production
vercel --prod
```

### 4️⃣ Update CORS in Backend
After getting your Vercel URL:
1. Edit `api_server.py`
2. Add your Vercel URL to `allow_origins` list
3. Commit and push:
   ```bash
   git add api_server.py
   git commit -m "Update CORS for Vercel domain"
   git push origin develop
   ```
   (GitHub Action will auto-sync to deploy branch)

---

## 🔄 Future Updates

To deploy updates:
```bash
# Make your code changes
git add .
git commit -m "Your update message"
git push origin develop
```

GitHub Action automatically syncs to `deploy` branch → Render auto-deploys backend → Vercel auto-deploys frontend!

---

## 📁 Key Files Added

- ✅ `render.yaml` - Render configuration
- ✅ `vercel.json` - Vercel configuration  
- ✅ `runtime.txt` - Python version for Render
- ✅ `Procfile` - Start command for Render
- ✅ `.github/workflows/sync-deploy.yml` - Auto-sync develop → deploy
- ✅ `DEPLOYMENT_GUIDE.md` - Full deployment instructions
- ✅ `.env.example` - Template for environment variables

---

## 🌐 Your URLs

After deployment:
- **Backend API**: `https://cognitive-ai-tutor-backend.onrender.com`
- **Frontend**: `https://your-project-name.vercel.app`

Test backend: Visit backend URL, should see:
```json
{"status":"Cognitive Adaptive AI Tutor API running","version":"2.0.0"}
```
