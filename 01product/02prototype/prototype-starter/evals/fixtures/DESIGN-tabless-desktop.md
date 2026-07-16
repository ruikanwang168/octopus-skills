---
name: Tabless Desktop Portal
language: zh-CN
summary: 经确认的无工作页签桌面门户，用于通用布局回归评测。
initialization:
  productMode: greenfield
  confirmationStatus: confirmed
tokens:
  colors:
    text: "#1f2430"
    surface: "#ffffff"
    canvas: "#f4f7fb"
  typography:
    baseFontFamily: "Arial, sans-serif"
layout:
  contractVersion: 2
  profiles:
    - id: portal-main
      productForm: portal
      rootRegion: portal-root
      viewports:
        - id: desktop
          category: desktop
          width: 1440
          height: 900
          claim: fidelity
      breakpoints: []
      regions:
        - id: portal-root
          role: root
          selector: ".portal-app"
          parent: null
          presence:
            desktop: required
          styles:
            base:
              minHeight: 900
              background: "{tokens.colors.canvas}"
              color: "{tokens.colors.text}"
              fontFamily: "{tokens.typography.baseFontFamily}"
        - id: portal-header
          role: header
          selector: ".portal-header"
          parent: portal-root
          before: portal-content
          presence:
            desktop: required
          geometry:
            desktop:
              height: 72
          styles:
            base:
              background: "{tokens.colors.surface}"
        - id: portal-content
          role: content
          selector: ".portal-content"
          parent: portal-root
          before: portal-footer
          presence:
            desktop: required
          styles:
            base:
              maxWidth: 1180
              margin: "0 auto"
        - id: route-tabs
          role: route-tabs
          selector: ".route-tabs"
          parent: portal-content
          presence:
            desktop: absent
        - id: portal-footer
          role: footer
          selector: ".portal-footer"
          parent: portal-root
          presence:
            desktop: required
          geometry:
            desktop:
              height: 64
      scrollOwner:
        desktop: body
components: {}
pageTemplates:
  - id: portal-home
    name: 服务门户
    purpose: 展示没有工作页签的门户内容
    representative: true
    layoutProfile: portal-main
    structure:
      - portal-root
      - portal-header
      - portal-content
      - portal-footer
    components: []
    previewContent:
      regions:
        portal-header:
          text: 服务门户
        portal-footer:
          text: 服务支持中心
      blocks:
        - id: title
          type: heading
          level: 1
          text: 常用服务
generationRules:
  noSource:
    - 缺少布局、业务内容或视觉值时停止并询问用户
  selfCheck:
    - 页面不得生成工作页签
evidence:
  decisions:
    - path: layout.profiles.portal-main
      decision: 桌面门户明确不包含工作页签
      source: user-confirmed
      confirmedAt: "2026-07-14T00:00:00+08:00"
---

# 无页签桌面门户

所有布局事实均来自已确认契约。
