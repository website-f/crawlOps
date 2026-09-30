import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { PostDetailPanel } from './components/PostDetailPanel'
import { PostDetailProvider } from './components/postdetail-ctx'
import { OverlayProvider } from './components/ui/overlays'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <OverlayProvider>
        <PostDetailProvider>
          <App />
          <PostDetailPanel />
        </PostDetailProvider>
      </OverlayProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
