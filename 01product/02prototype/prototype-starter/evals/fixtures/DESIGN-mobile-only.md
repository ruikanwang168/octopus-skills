---
name: Mobile Only Web App
language: zh-CN
summary: 只支持移动 Web 的经确认产品，只有内容区和底部导航。
initialization:
  productMode: greenfield
  confirmationStatus: confirmed
tokens:
  colors:
    text: "#20232a"
    surface: "#ffffff"
    canvas: "#f5f3ff"
  typography:
    baseFontFamily: "Arial, sans-serif"
layout:
  contractVersion: 2
  profiles:
    - id: mobile-main
      productForm: mobile-web
      rootRegion: product-root
      viewports:
        - id: phone
          category: mobile
          width: 390
          height: 844
          claim: fidelity
      breakpoints: []
      regions:
        - id: product-root
          role: root
          selector: ".mobile-app"
          parent: null
          presence:
            phone: required
          styles:
            base:
              display: flex
              flexDirection: column
              background: "{tokens.colors.canvas}"
              color: "{tokens.colors.text}"
              fontFamily: "{tokens.typography.baseFontFamily}"
        - id: content
          role: content
          selector: ".mobile-content"
          parent: product-root
          before: bottom-nav
          presence:
            phone: required
          styles:
            base:
              flex: 1
        - id: route-tabs
          role: route-tabs
          selector: ".route-tabs"
          parent: content
          presence:
            phone: absent
        - id: bottom-nav
          role: bottom-navigation
          selector: ".bottom-nav"
          parent: product-root
          presence:
            phone: required
          geometry:
            phone:
              height: 56
          styles:
            base:
              display: flex
              background: "{tokens.colors.surface}"
      scrollOwner:
        phone: content
components: {}
pageTemplates:
  - id: home
    name: 移动首页
    purpose: 展示移动产品首页和底部导航
    representative: true
    layoutProfile: mobile-main
    structure:
      - product-root
      - content
      - bottom-nav
    components: []
    previewContent:
      regions:
        bottom-nav:
          items:
            - 首页
            - 我的
      blocks:
        - id: title
          type: heading
          level: 1
          text: 移动首页
generationRules:
  noSource:
    - 缺少布局、业务内容或视觉值时停止并询问用户
  selfCheck:
    - 页面不得生成桌面布局、侧栏或工作页签
evidence:
  decisions:
    - path: layout.profiles.mobile-main
      decision: 产品仅支持 390×844 移动视口，不包含桌面端、侧栏或工作页签
      source: user-confirmed
      confirmedAt: "2026-07-14T00:00:00+08:00"
---

# 纯移动 Web 产品

未声明桌面端布局和证据。
