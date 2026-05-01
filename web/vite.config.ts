import { defineConfig, type PluginOption } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'

const SHORTLIST_PATH = path.resolve(import.meta.dirname, '..', 'shortlist.json')

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

export default defineConfig({
  plugins: [react(), tailwindcss(), shortlistApi()],
})
