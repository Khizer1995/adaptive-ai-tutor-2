# Cognitive Adaptive AI Tutor - Frontend

React + Vite frontend for the Cognitive Adaptive AI Tutor learning platform.

## Tech Stack

- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **Routing**: React Router
- **HTTP Client**: Axios
- **Authentication**: Supabase Auth

---

## Prerequisites

- Node.js 16+ and npm
- Backend API server running on http://localhost:8765

---

## Installation

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Configure .env with your values:
# VITE_API_BASE_URL=http://127.0.0.1:8765
# VITE_SUPABASE_URL=your_supabase_url
# VITE_SUPABASE_ANON_KEY=your_anon_key
```

---

## Development

```bash
# Start development server
npm run dev

# Frontend will run on http://localhost:5173
# (or the next available port)
```

The development server includes:
- Hot Module Replacement (HMR) for instant updates
- Fast refresh for React components
- Source maps for debugging

---

## Building for Production

```bash
# Create optimized production build
npm run build

# Preview production build locally
npm run preview
```

Build output will be in the `dist/` directory.

---

## Project Structure

```
ui/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/          # Route pages
│   ├── context/        # React context providers
│   ├── services/       # API service layer
│   ├── hooks/          # Custom React hooks
│   ├── utils/          # Helper functions
│   └── App.jsx         # Main app component
├── public/             # Static assets
├── index.html          # HTML template
├── vite.config.js      # Vite configuration
├── tailwind.config.js  # Tailwind CSS config
└── package.json        # Dependencies
```

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend API URL | `http://127.0.0.1:8765` |
| `VITE_SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJhbGc...` |

---

## Features

- 🔐 **Authentication**: Sign up, login, logout with Supabase
- 📚 **Topic Browser**: Navigate DSA topics (Arrays, Queues, Graphs)
- 📖 **Adaptive Learning**: Get personalized explanations based on your level
- ✅ **Interactive Quizzes**: Practice with MCQs that adapt to your performance
- 📊 **Progress Tracking**: View mastery levels and learning analytics
- 🎯 **Assessments**: Pretest and posttest for each topic

---

## Connecting to Backend

The frontend connects to the backend API at the URL specified in `VITE_API_BASE_URL`.

**Default development setup:**
- Backend: http://localhost:8765
- Frontend: http://localhost:5173

Make sure the backend server is running before starting the frontend.

---

## Troubleshooting

**Port already in use:**
```bash
# Vite will automatically use the next available port
# Check the terminal output for the actual URL
```

**API connection issues:**
```bash
# Verify backend is running on port 8765
# Check that VITE_API_BASE_URL in .env matches backend URL
# Check browser console for CORS errors
```

**Build errors:**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

---

## Deployment

The frontend is configured for deployment to Vercel.

```bash
# Deploy to Vercel
vercel deploy

# Or connect your Git repository to Vercel
# for automatic deployments on push
```

Environment variables must be configured in the Vercel dashboard.

---

## Learn More

- [Vite Documentation](https://vitejs.dev)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Supabase Auth](https://supabase.com/docs/guides/auth)
