import { defineConfig, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import yaml from 'js-yaml'

const SHORTLIST_PATH = path.resolve(import.meta.dirname, '..', 'shortlist.json')
const PLAN_PATH = path.resolve(import.meta.dirname, '..', 'plan.yaml')
const PLAN_OUT = path.resolve(import.meta.dirname, 'public', 'plan.json')

function shortlistApi(): PluginOption {
  return {
    name: 'shortlist-api',
    configureServer(server) {
      server.middlewares.use('/api/shortlist', async (req, res) => {
        try {
          if (req.method === 'GET') {
            const body = existsSync(SHORTLIST_PATH)
              ? await readFile(SHORTLIST_PATH, 'utf-8')
              : '[]'
            res.setHeader('Content-Type', 'application/json')
            res.end(body)
            return
          }
          if (req.method === 'POST') {
            let raw = ''
            for await (const chunk of req) raw += chunk
            const parsed = JSON.parse(raw)
            if (!Array.isArray(parsed) || !parsed.every(n => typeof n === 'number')) {
              res.statusCode = 400
              res.end('expected JSON array of numbers')
              return
            }
            await writeFile(SHORTLIST_PATH, JSON.stringify(parsed, null, 2) + '\n', 'utf-8')
            res.statusCode = 204
            res.end()
            return
          }
          res.statusCode = 405
          res.end()
        } catch (err) {
          res.statusCode = 500
          res.end(String(err))
        }
      })
    },
  }
}

function planApi(): PluginOption {
  return {
    name: 'plan-api',
    configureServer(server) {
      server.middlewares.use('/api/plan', async (_req, res) => {
        try {
          const raw = await readFile(PLAN_PATH, 'utf-8')
          const parsed = yaml.load(raw)
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(parsed))
        } catch (err) {
          res.statusCode = 500
          res.end(String(err))
        }
      })
      server.watcher.add(PLAN_PATH)
      server.watcher.on('change', file => {
        if (file === PLAN_PATH) server.ws.send({ type: 'full-reload' })
      })
    },
    async buildStart() {
      // Bake plan.yaml -> public/plan.json so production builds have a static asset
      // at /plan.json. Dev hits /api/plan instead and never reads this file.
      const raw = await readFile(PLAN_PATH, 'utf-8')
      const parsed = yaml.load(raw)
      await mkdir(path.dirname(PLAN_OUT), { recursive: true })
      await writeFile(PLAN_OUT, JSON.stringify(parsed), 'utf-8')
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), shortlistApi(), planApi()],
})
