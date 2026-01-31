# 🎨 Web App Visual Guide

## What You'll See

### Main Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL MVCC Bloat Visualizer                              │
│  Real-time observation of dead tuple accumulation...           │
├─────────────────────────────────────────────────────────────────┤
│  [Historical Data]  [Live View]                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Available Experiments                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │ bloat-demo   │ │toast-mutation│ │ read-heavy   │          │
│  │ 2026-01-27   │ │ 2026-01-27   │ │ 2026-01-26   │          │
│  │ 300s, 60pts  │ │ 300s, 60pts  │ │ 300s, 60pts  │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Storage Growth Chart

```
Storage (MB)
3000 ┤                                                       ╭─ Total
     │                                                    ╭─╯
2500 ┤                                                 ╭─╯
     │                                             ╭──╯
2000 ┤                                         ╭──╯        ╭─ TOAST
     │                                     ╭──╯        ╭──╯
1500 ┤                                 ╭──╯        ╭──╯
     │                             ╭──╯        ╭──╯
1000 ┤                         ╭──╯        ╭──╯
     │                     ╭──╯        ╭──╯              ╭─ Indexes
 500 ┤                 ╭──╯        ╭──╯            ╭───╯
     │             ╭──╯        ╭──╯          ╭────╯       ╭─ Table
   0 ┼─────────────────────────────────────────────────────
     0    50   100   150   200   250   300 (seconds)
```

### Dead Tuples Chart

```
Tuples (thousands)
600 ┤                                              ┌─────────┐
    │                                         ┌────┤ DEAD    │
500 ┤                                    ┌────┘    │ TUPLES  │
    │                               ┌────┘         └─────────┘
400 ┤                          ┌────┘
    │                     ┌────┘
300 ┤                ┌────┘
    │           ┌────┘                   ┌─────────┐
200 ┤      ┌────┘                        │ LIVE    │
    │ ┌────┘                             │ TUPLES  │
100 ┤─┘                                  └─────────┘
    │
  0 ┼────────────────────────────────────────────────
    0    50   100   150   200   250   300 (seconds)
```

### HOT Update Ratio

```
Ratio (%)
100 ┤
    │
 75 ┤
    │
 50 ┤
    │
 25 ┤
    │
  0 ┼────────────────────────────────────────────────
    0    50   100   150   200   250   300 (seconds)
    
    Flatline at 0% - JSONB updates prevent HOT!
```

### Buffer Cache Hit Ratio

```
Hit Ratio (%)
100 ┤                   ┌─────────────────────────────
    │                ┌──┘
 95 ┤             ┌──┘
    │          ┌──┘
 90 ┤       ┌──┘
    │    ┌──┘
 85 ┤ ┌──┘
    │─┘
 80 ┼────────────────────────────────────────────────
    0    50   100   150   200   250   300 (seconds)
    
    High cache hits but still slow due to dead tuples!
```

## Live View Mode

```
┌─────────────────────────────────────────────────────────────────┐
│  Live Metrics                                 ● Connected       │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ Dead Tuples  │ │ Dead Ratio   │ │ TOAST Size   │           │
│  │ 453,892      │ │   81.9%      │ │   1.85 GB    │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│  ┌──────────────┐                                              │
│  │ Total Size   │                                              │
│  │   2.42 GB    │                                              │
│  └──────────────┘                                              │
│                                                                 │
│  [Real-time charts updating every 5 seconds...]                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Color Scheme

### Chart Colors
- **Blue** (#58a6ff) - Table size, primary metrics
- **Red** (#f85149) - TOAST size, dead tuples (danger!)
- **Orange** (#ffa657) - Index size, warnings
- **Purple** (#a371f7) - Total size, cache metrics
- **Green** (#3fb950) - Live tuples, success states

### UI Colors
- **Background** (#0f1419) - Deep dark
- **Cards** (#161b22) - Slightly lighter
- **Borders** (#30363d) - Subtle separation
- **Text** (#e6edf3) - High contrast white

## Responsive Behavior

### Desktop (>1200px)
```
┌─────────────┬─────────────┐
│  Storage    │ Dead Tuples │
│  Chart      │  Chart      │
├─────────────┼─────────────┤
│ HOT Updates │ Cache Hits  │
│  Chart      │  Chart      │
└─────────────┴─────────────┘
```

### Tablet (768-1200px)
```
┌─────────────┐
│  Storage    │
│  Chart      │
├─────────────┤
│ Dead Tuples │
│  Chart      │
├─────────────┤
│ HOT Updates │
│  Chart      │
├─────────────┤
│ Cache Hits  │
│  Chart      │
└─────────────┘
```

### Mobile (<768px)
```
┌───────────┐
│  Storage  │
│   Chart   │
├───────────┤
│   Dead    │
│  Tuples   │
├───────────┤
│    HOT    │
│  Updates  │
├───────────┤
│   Cache   │
│   Hits    │
└───────────┘
```

## Interaction Patterns

### Experiment Selection
1. Click experiment card → Highlights with blue border
2. Charts automatically load and render
3. Smooth fade-in animation
4. Tooltips on hover

### Chart Interaction
1. Hover over chart → Tooltip shows exact values
2. Legend toggle → Click to show/hide series
3. Zoom (future) → Drag to zoom time range
4. Export (future) → Download as PNG

### View Mode Toggle
1. Click "Live View" → Switches mode instantly
2. Starts 5-second polling
3. Connection indicator shows status
4. Stats cards update in real-time

## Loading States

### Initial Load
```
┌─────────────────────────────────────┐
│  Loading experiments...             │
│  ●●●●●○○○○○                         │
└─────────────────────────────────────┘
```

### Chart Loading
```
┌─────────────────────────────────────┐
│  Storage Growth Over Time           │
│                                     │
│  Loading metrics...                 │
│  ●●●●●○○○○○                         │
└─────────────────────────────────────┘
```

### Live View Connecting
```
┌─────────────────────────────────────┐
│  Live Metrics     ● Connecting...   │
└─────────────────────────────────────┘
```

## Error States

### No Experiments
```
┌─────────────────────────────────────┐
│  No experiments found               │
│  Run: make experiment PRESET=...    │
└─────────────────────────────────────┘
```

### Connection Error
```
┌─────────────────────────────────────┐
│  Live Metrics     ● Connection Error│
│                                     │
│  Cannot connect to PostgreSQL       │
│  Check that the database is running │
└─────────────────────────────────────┘
```

### API Error
```
┌─────────────────────────────────────┐
│  Error: Failed to fetch metrics     │
│  Please try again later             │
└─────────────────────────────────────┘
```

## Animation Examples

### Page Load
```
Fade in: 0 → 100% opacity (300ms)
Slide up: +20px → 0px (300ms, ease-out)
```

### Chart Render
```
Draw lines: 0% → 100% length (500ms, ease-in-out)
Fade in axes: 0 → 100% opacity (200ms)
```

### Status Dot Pulse
```
Opacity: 100% → 50% → 100% (2s, infinite)
Scale: 1.0 → 1.1 → 1.0 (2s, infinite)
```

### Card Hover
```
Transform: translateY(0) → translateY(-2px) (200ms)
Box-shadow: 0 → 0 4px 12px rgba(88,166,255,0.2)
Border: #30363d → #58a6ff
```

## Typography

### Headers
- H1: 2.5rem (40px), Bold - Page title
- H2: 1.5rem (24px), Semi-bold - Section headers
- H3: 1.3rem (21px), Medium - Chart titles

### Body
- Regular: 0.95rem (15px) - Main text
- Small: 0.85rem (14px) - Timestamps
- Tiny: 0.8rem (13px) - Chart labels

### Monospace
- Code: Monaco, Menlo - For run IDs, stats

## Icons & Indicators

### Connection Status
- 🟢 Connected (green dot)
- 🟡 Connecting... (yellow dot, pulsing)
- 🔴 Error (red dot)

### Experiment Status
- ✓ Complete (in list)
- ⟳ Running (in live view)
- ✗ Failed (error state)

## Accessibility

### Keyboard Navigation
- Tab: Move between controls
- Enter: Select experiment
- Space: Toggle view mode
- Esc: Close modals (future)

### Screen Readers
- Semantic HTML (header, nav, main, footer)
- ARIA labels on charts
- Alt text on icons
- Live region updates

### Color Contrast
- WCAG AA compliant
- Minimum 4.5:1 ratio
- Text on backgrounds clearly readable
- Chart colors distinguishable

## What Makes It Special

1. **Real-time Updates** - Watch bloat happen live
2. **Beautiful Charts** - Professional D3.js visualizations
3. **Dark Mode** - Easy on the eyes, GitHub-style
4. **Responsive** - Works on all devices
5. **Intuitive** - No training needed
6. **Fast** - Instant chart rendering
7. **Educational** - See MVCC concepts visually

---

**The interface makes complex database behavior simple to understand!**
