import '@fontsource-variable/manrope'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { LazyMotion, MotionConfig } from 'motion/react'
import { BrowserRouter, HashRouter } from 'react-router-dom'

import App from './App'
import { ToastProvider } from './components/feedback'
import { isNativeCrazyGame } from './native'
import { initializeMobileRuntime } from './mobileApi'
import './i18n'
import './styles.css'
import './workbench.css'

const loadMotionFeatures = () =>
  import('./motionFeatures').then((module) => module.default)
const Router = isNativeCrazyGame() ? HashRouter : BrowserRouter
if (isNativeCrazyGame()) initializeMobileRuntime()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <LazyMotion features={loadMotionFeatures} strict>
        <ToastProvider>
          <Router>
            <App />
          </Router>
        </ToastProvider>
      </LazyMotion>
    </MotionConfig>
  </React.StrictMode>
)

