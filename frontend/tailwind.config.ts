import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        moose: {
          forest:    { DEFAULT: '#1A3A2A', hover: '#2D5A3F', light: '#3D7A53' },
          gold:      { DEFAULT: '#C8A84E', hover: '#B8942E', light: '#D4BC6E' },
          parchment: { DEFAULT: '#F5F0E8', dark: '#E8DFD0' },
          leather:   { DEFAULT: '#8B7355', dark: '#2C2416' },
        },
        confidence: {
          high:   '#2E7D32',
          medium: '#F57F17',
          low:    '#E65100',
          none:   '#C62828',
        },
      },
      fontFamily: {
        heading: ['Playfair Display', 'Georgia', 'serif'],
        body:    ['Inter', '-apple-system', 'sans-serif'],
        legal:   ['Georgia', 'Times New Roman', 'serif'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};

export default config;
