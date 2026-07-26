# Landing Page

> Tổng hợp kiến thức về xây dựng landing page quảng bá app mobile (dark theme, neon gradient) trong dự án.
> Cập nhật lần cuối: 2026-04-25

---

## Architecture

### Dark Neon Landing Page — Design System Structure
- **Ngày**: 2026-04-25
- **Chi tiết**: CSS tổ chức theo thứ tự: Reset → Tokens (CSS Custom Properties) → Base → Components → Animations → Responsive → Reduced Motion. Toàn bộ màu, font, spacing, radius, shadow, transition được khai báo qua CSS variables trong `:root`. Không dùng framework, chỉ vanilla HTML/CSS/JS. Font combo: Space Grotesk (heading) + Inter (body) từ Google Fonts.
- **Files liên quan**: `css/style.css`, `index.html`

### Single-Page Section Layout
- **Ngày**: 2026-04-25
- **Chi tiết**: Landing page gồm 7 sections theo thứ tự conversion funnel: Navbar (sticky) → Hero (hook + CTA) → Features (value props) → How It Works (simplicity) → Stats (social proof) → Testimonials (trust) → Download CTA (final conversion) → Footer. Mỗi section có `id` riêng cho smooth scroll navigation.
- **Files liên quan**: `index.html`

---

## Bugs & Solutions

### Mobile menu hiển thị trên desktop — z-index overlap
- **Ngày**: 2026-04-25
- **Vấn đề**: `.mobile-menu` div không có CSS rule mặc định, chỉ có styles trong `@media (max-width: 768px)`. Trên desktop, nó render với default styles (static position, visible) và bị navbar đè lên.
- **Root cause**: Thiếu `display: none` ở base CSS cho `.mobile-menu`. Styles chỉ nằm trong media query nên desktop không áp dụng.
- **Fix**: Thêm `.mobile-menu { display: none; }` ngay sau hamburger styles, trước media query. Trong media query 768px, override bằng `display: flex` + `transform: translateX(100%)`.
- **Files liên quan**: `css/style.css`

### CSS transition sử dụng CSS variable sai cú pháp
- **Ngày**: 2026-04-25
- **Vấn đề**: `.reveal` dùng `transition: opacity 0.7s var(--transition-base)` — nhưng `--transition-base` chứa `0.3s cubic-bezier(...)` (duration + easing), không phải chỉ easing function.
- **Root cause**: CSS variable chứa cả duration lẫn timing function, khi ghép vào transition shorthand sẽ bị browser parse sai.
- **Fix**: Viết trực tiếp easing: `transition: opacity 0.7s cubic-bezier(0.4,0,0.2,1)` hoặc tách variable thành `--easing-base` riêng.
- **Files liên quan**: `css/style.css`

---

## How-To

### Tạo landing page dark neon cho app mobile
- **Ngày**: 2026-04-25
- **Bước thực hiện**:
  1. Lấy thông tin app từ Google Play URL bằng `read_url_content`
  2. Tạo file structure: `index.html`, `css/style.css`, `js/main.js`, `assets/images/`
  3. Generate assets: phone mockup + abstract background bằng `generate_image`
  4. Xóa nền ảnh mockup bằng Python `rembg` (`pip3 install rembg onnxruntime`)
  5. Viết CSS design system (tokens → base → components → animations → responsive)
  6. Viết HTML sections theo conversion funnel
  7. Viết JS: scroll reveal (IntersectionObserver), stat counter (requestAnimationFrame), navbar scroll, mobile menu, smooth scroll
  8. Test trên browser, fix bugs
- **Files liên quan**: `index.html`, `css/style.css`, `js/main.js`

### Xóa nền ảnh bằng Python rembg
- **Ngày**: 2026-04-25
- **Bước thực hiện**:
  1. `pip3 install rembg pillow onnxruntime`
  2. Script Python: `from rembg import remove` → đọc file binary → `remove(input_data)` → save PNG
  3. Lần chạy đầu sẽ tải model (~30s), các lần sau nhanh hơn
  4. Output là PNG với transparent background
- **Files liên quan**: `assets/images/hero-phone.png`

---

## Patterns

### IntersectionObserver cho scroll reveal + stat counter
- **Ngày**: 2026-04-25
- **Chi tiết**: Dùng 2 IntersectionObserver riêng biệt: (1) `revealObserver` với threshold 0.15 cho fade-in elements, auto `unobserve` sau khi visible; (2) `statsObserver` với threshold 0.3 cho counter animation, dùng flag `countersDone` để chỉ trigger 1 lần rồi `disconnect()`. Counter animation dùng `requestAnimationFrame` + cubic easing `1 - Math.pow(1 - progress, 3)`.
- **Files liên quan**: `js/main.js`

### CSS gradient text pattern
- **Ngày**: 2026-04-25
- **Chi tiết**: `.gradient-text` dùng `background: linear-gradient(...)` + `background-clip: text` + `-webkit-text-fill-color: transparent`. Cần cả `-webkit-background-clip` cho Safari compatibility. Dùng 3 màu gradient (purple → cyan → mint) cho hiệu ứng colorful hơn 2 màu.
- **Files liên quan**: `css/style.css`

### Mobile menu toggle pattern
- **Ngày**: 2026-04-25
- **Chi tiết**: Base CSS: `display: none`. Media query ≤768px: `display: flex` + `transform: translateX(100%)`. Toggle class `.open` → `translateX(0)`. Khi mở: `body.style.overflow = 'hidden'` để ngăn scroll behind. Khi click link trong menu: auto close menu + restore overflow. Hamburger icon: 3 spans, `.active` xoay span 1/3 thành X, ẩn span 2.
- **Files liên quan**: `css/style.css`, `js/main.js`
