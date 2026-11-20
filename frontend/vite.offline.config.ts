// Explicit local fallback when npm is blocked. Uses the same React application
// and authored CSS; skips Tailwind's reset/utilities. Normal deployment uses vite.config.ts.
import {defineConfig} from 'vite';
export default defineConfig({plugins:[{name:'offline-authored-css',enforce:'pre',transform(code,id){if(id.endsWith('.css'))return code.replace('@import "tailwindcss";','');}}],server:{host:'127.0.0.1',proxy:{'/api':'http://127.0.0.1:8000'}}});
