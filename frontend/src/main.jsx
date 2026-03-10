import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Apply saved theme synchronously before first paint to avoid flash
;(function () {
  const saved = localStorage.getItem('kln-theme') ?? 'light'
  document.documentElement.setAttribute('data-theme', saved)
})()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
