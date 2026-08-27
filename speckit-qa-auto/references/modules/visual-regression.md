# Visual Regression Testing Module

Read this module **only when visual screenshot comparisons are specified** in scenario designs.

## 1. Baseline & Snapshot Rules

Playwright natively supports visual comparisons via `toHaveScreenshot()`:
```typescript
await expect(page).toHaveScreenshot('login-page.png', {
  maxDiffPixelRatio: 0.02, // Allow up to 2% pixel difference for minor rendering variations
  fullPage: true,
});
```

## 2. Best Practices for Stable Visual Tests

1. **Mask Dynamic Content**: Always mask timestamps, dynamic user IDs, or animated elements:
   ```typescript
   await expect(page).toHaveScreenshot({
     mask: [page.locator('.timestamp'), page.locator('.avatar')],
   });
   ```
2. **Disable Animations**: Ensure CSS animations/transitions are disabled before capturing:
   ```typescript
   await page.emulateMedia({ reducedMotion: 'reduce' });
   ```
3. **Consistent Environment**: Generate baselines in headless mode in the target OS/Docker runner.
