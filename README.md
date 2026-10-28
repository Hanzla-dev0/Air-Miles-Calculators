# Air Miles Calculators – static site

Main keyword: **air miles calculator**

## Deploy
Upload the contents of `site/` to the web root of airmilescalculators.com (Netlify, Cloudflare Pages, Vercel, Apache, Nginx or any static host). No server code or database is needed.

## Rebuild after changes
    python3 build/build.py      # regenerates ./site
    python3 -I build/verify.py site   # checks titles, H1s, canonicals, links, JSON-LD, sitemap

## What to edit
- `build/build.py` – domain (`BASE`), brand, contact email, all page templates and copy
- `build/airports_data.py` – `AIRPORTS` (IATA, name, city, country, lat, lon) and `ROUTES` (pairs that get their own page)
- `build/assets/` – `style.css` and `app.js`

## Before launch checklist
1. Replace `contact@airmilescalculators.com` with a real mailbox (`CONTACT_EMAIL`).
2. Add the site in Google Search Console and Bing Webmaster Tools, then submit `https://airmilescalculators.com/sitemap.xml`.
3. Have the Privacy Policy and Terms reviewed (they are plain templates, not legal advice) and update them if you add analytics or ads.
4. Expand `AIRPORTS` using a full open dataset such as OurAirports or OpenFlights (the bundled list has 128 major airports).

## SEO built in
Single H1 per page, unique title and meta description, canonical and hreflang tags, Open Graph and Twitter cards, JSON-LD (Organization, WebSite, WebApplication, FAQPage, BreadcrumbList, Airport, Article), `sitemap.xml`, `robots.txt`, semantic HTML, mobile-first CSS with no external requests, and clean trailing-slash URLs.
