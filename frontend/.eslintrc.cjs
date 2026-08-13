/* eslint-env node */
// .cjs because package.json sets "type": "module" — eslint 8's rc loader needs CommonJS.
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    // essential = correctness rules only; formatting stays with prettier
    'plugin:vue/vue3-essential',
    'plugin:@typescript-eslint/recommended',
  ],
  // vue-eslint-parser handles the SFC shell; @typescript-eslint/parser handles
  // <script lang="ts"> blocks and plain .ts files.
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
    extraFileExtensions: ['.vue'],
  },
  rules: {
    'vue/multi-word-component-names': 'off',
  },
}
