---
name: 開票小精靈
description: 螢火蟲小精靈陪你把模糊的需求拷問成 Spec，再以自己的身份開成 ADO 票
colors:
  night-forest: "#2e7d4f"
  night-forest-deep: "#1f5e3a"
  night-forest-mist: "#e3f2e3"
  leaf-green: "#1f6b45"
  firefly-glow: "#f4c542"
  burnt-amber: "#8a4b08"
  burnt-amber-mist: "#fcefd9"
  amber-line: "#e9a23b"
  ember-red: "#b42323"
  ember-mist: "#fdecec"
  deep-pine-ink: "#1c2b22"
  pine-ink-soft: "#33463a"
  moss: "#56695c"
  meadow-paper: "#f3f7f0"
  paper-white: "#ffffff"
  sage-wash: "#edf4ea"
  sage-border: "#dce8da"
  sage-border-strong: "#c9dcc8"
  field-border: "#7f9586"
  sprite-face: "#fff6e5"
  sprite-wing: "#d9eef0"
  sprite-blush: "#f6b8a0"
typography:
  display:
    fontFamily: "Huninn, Noto Sans TC, sans-serif"
    fontSize: "28px"
    fontWeight: 400
    lineHeight: 1.3
  headline:
    fontFamily: "Huninn, Noto Sans TC, sans-serif"
    fontSize: "20px"
    fontWeight: 400
  title:
    fontFamily: "Huninn, Noto Sans TC, sans-serif"
    fontSize: "17px"
    fontWeight: 400
  body:
    fontFamily: "Noto Sans TC, -apple-system, BlinkMacSystemFont, Segoe UI, PingFang TC, Microsoft JhengHei, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Noto Sans TC, sans-serif"
    fontSize: "13px"
    fontWeight: 400
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 500
rounded:
  sm: "12px"
  md: "18px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.night-forest}"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
  button-default:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.deep-pine-ink}"
    rounded: "{rounded.pill}"
    padding: "7px 16px"
  button-default-hover:
    backgroundColor: "{colors.sage-wash}"
  button-link:
    textColor: "{colors.night-forest}"
    padding: "2px 4px"
  segmented-on:
    backgroundColor: "{colors.night-forest}"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.pill}"
  option-on:
    backgroundColor: "{colors.night-forest-mist}"
    textColor: "{colors.deep-pine-ink}"
    rounded: "{rounded.sm}"
    padding: "9px 13px"
    height: "44px"
  card:
    backgroundColor: "{colors.paper-white}"
    rounded: "{rounded.md}"
    padding: "16px"
  input:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.deep-pine-ink}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  badge:
    backgroundColor: "{colors.sage-wash}"
    textColor: "{colors.moss}"
    rounded: "{rounded.pill}"
    padding: "1px 8px"
  badge-premise:
    backgroundColor: "{colors.burnt-amber-mist}"
    textColor: "{colors.burnt-amber}"
    rounded: "{rounded.pill}"
  notice-warn:
    backgroundColor: "{colors.burnt-amber-mist}"
    textColor: "{colors.burnt-amber}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  notice-danger:
    backgroundColor: "{colors.ember-mist}"
    textColor: "{colors.ember-red}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
  tooltip:
    backgroundColor: "{colors.deep-pine-ink}"
    textColor: "{colors.meadow-paper}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
---

# Design System: 開票小精靈

## Overview

**Creative North Star: "螢火蟲的寫字桌"（The Firefly's Desk）**

一張安靜的淡綠色寫字桌。紙是白的，桌面是帶一點草地氣息的淡綠，所有東西都圓圓軟軟、伸手就按得到。桌邊停著一隻螢火蟲小精靈，牠點著一盞小燈，幫你翻 Knowledge Source、把一輪輪的問答整理成 Spec。光從牠身上來：螢火黃只屬於小精靈和「還差多少」的進度感；夜林綠是桌上唯一的行動色。

介面密度偏舒適：單欄閱讀寬度（980px），拷問頁才展開成主欄加側欄。層次主要靠淡綠底色的深淺與細邊線，陰影只用在「現在輪到你」的地方。燒糖琥珀標出所有「還沒確定」的東西（Premise、Open Question、警告），讓人一眼看出 Spec 哪裡還虛。

方向上，這個系統**歡迎更多個性**：小精靈的姿勢、螢火的微光、口語化的文案，可以比現在更大方地出現在空狀態、完成時刻與等待畫面中。前提是不干擾作答與開票這條主路徑，也不增加 PM / FAE 的負擔。

**Key Characteristics:**
- 淡綠紙面、白色卡片、深松墨文字，整體低對比、溫和
- 膠囊按鈕與大圓角卡片，幾乎不用陰影
- 夜林綠是唯一的行動色；螢火黃是小精靈的專屬光
- 燒糖琥珀 = 未確定（Premise、Open Question、Assumption 相關警告）
- Huninn 圓體做標題，帶出手寫、親切的語氣；內文用 Noto Sans TC
- 完整的深色模式（「夜裡的寫字桌」），由同一組語意變數切換

## Colors

一座夜裡的森林：深淺不同的綠是骨架，螢火黃與燒糖琥珀是林間僅有的暖光。

### Primary
- **夜林綠 Night Forest**：主按鈕、連結、選中的切換鈕、「現在輪到你」的卡片框線，桌上唯一的行動色。
- **夜林深綠 Night Forest Deep**：淡綠底上的強調文字，例如「小精靈建議：」、範例主題、標籤內字。
- **夜林薄霧 Night Forest Mist**：選中選項的底、資訊提示、已回答的答案底色。
- **葉綠 Leaf Green**：成功狀態的文字（已開票、已回答）。

### Secondary
- **螢火 Firefly Glow**：只屬於小精靈：尾巴的光、讀書時的呼吸光暈、開票票券，以及題數進度條。它代表「小精靈在這裡」。

### Tertiary
- **燒糖琥珀 Burnt Amber**：所有「還沒確定」的訊號：Premise 徽章、警告提示、Open Question 計數、待回答。
- **燒糖琥珀薄霧 Burnt Amber Mist**：上述訊號的底色。
- **琥珀線 Amber Line**：待確認 Premise 卡片頂端的 4px 色條、新版 Spec 的外框。
- **餘燼紅 Ember Red** 與 **餘燼薄霧 Ember Mist**：錯誤與破壞性動作（刪除、取消連結）。

### Neutral
- **深松墨 Deep Pine Ink**：主要文字、小精靈的線條、tooltip 底色、「核心」徽章的反白底。
- **淺松墨 Pine Ink Soft**：次要內文，例如已解決題目的內容、AI 查證說明。
- **苔蘚 Moss**：輔助文字、標籤、未選中的導覽項目。
- **草地紙 Meadow Paper**：頁面底色。
- **白紙 Paper White**：卡片與輸入框。
- **鼠尾草淡染 Sage Wash**：次層表面：證據區塊、統計格、預設徽章、按鈕 hover。
- **鼠尾草邊線 / 深邊線 Sage Border / Strong**：卡片分隔線；選項按鈕與下拉選單的框線。
- **欄位邊線 Field Border**：輸入框、下拉、檔案按鈕的框線，至少 3:1，讓欄位一眼看得出來。

### Sprite Palette
- **小精靈臉 Sprite Face**、**翅膀 Sprite Wing**、**腮紅 Sprite Blush**：只用在 `Sprite` 插圖裡，不拿來當 UI 顏色。

深色模式的對應值定義在 `frontend/app/globals.css` 的 `prefers-color-scheme: dark` 區塊（夜林綠提亮為 `#6cc28c`，琥珀提亮為 `#f0b45a`），元件一律透過語意變數取色。

### Named Rules
**The One Lamp Rule.** 螢火黃只屬於小精靈與「進度」。不要拿它當按鈕、連結或一般強調色；它一出現，就代表小精靈在場。

**The Amber Means Unsure Rule.** 燒糖琥珀只標示未確定的內容：Premise、Open Question、待回答、警告。不要拿它做裝飾或品牌點綴，否則使用者就分不出 Spec 哪裡還虛。

## Typography

**Display Font:** Huninn（後備 Noto Sans TC、sans-serif）
**Body Font:** Noto Sans TC（後備系統中文字型）
**Label/Mono Font:** JetBrains Mono（後備 ui-monospace）

**Character:** Huninn 是圓潤的手寫感圓體，讓標題像小精靈在說話；Noto Sans TC 負責清楚、中性的閱讀。等寬字只用在 Knowledge Source 的檔名與題號，提醒「這是查證過的出處」。

### Hierarchy
- **Display**（400、28px、1.3）：頁面標題，例如需求標題、「新增需求」。
- **Headline**（400、20px）：區塊標題，例如「第 N 輪」「Spec 預覽」「開票」。
- **Title**（400、17px）：題目標題、等待卡片標題、側欄標題。
- **Body**（400、15px、1.6）：一般內文；待回答題目的內容放大到 16px。
- **Label**（400、13px）：欄位標籤、輔助說明、步驟條；徽章 12px。
- **Mono**（500、12px）：題號（Q1、P2）與讀過的檔案路徑。

### Named Rules
**The Round Voice Rule.** Huninn 只用在標題與品牌字（h1–h3、logo 文字），而且永遠是 400 字重。不要加粗，也不要拿它排內文。

## Layout

- 單欄容器最大寬度 980px，左右留白 16px，底部留 80px 給浮動操作列。
- 拷問頁放寬到 1200px，分成主欄（彈性，最小 560px）與側欄（最小 280px）。側欄「Spec 成形中」黏在頂部（距頂 76px）；寬度不夠時自動換到主欄下方。
- 間距節奏是 4 的倍數，偏舒適：元件內 6–8px、堆疊 12px、卡片內 16px、拷問頁區塊 20–24px。
- 頂部導覽列黏在頂端；拷問中的「夠了，產出 Spec」操作列黏在底部（距底 12px）。
- 640px 以下：導覽列縮小左右留白，兩欄表單（`grid-2`）改成單欄。範例卡片用 `auto-fit` 最小 220px 自動排欄。

## Elevation & Depth

以色調分層為主，幾乎是平的。卡片靠白紙在草地紙上的明度差加一條鼠尾草細線分出層次，靜止時只有 1px 的極淡陰影，深色模式完全不用陰影。

### Shadow Vocabulary
- **Rest**（`box-shadow: 0 1px 2px rgba(28, 43, 34, 0.05)`）：所有卡片的預設，幾乎看不見。
- **Lift**（`box-shadow: 0 10px 28px -16px rgba(46, 125, 79, 0.45)`）：帶綠色調的浮起，只給「需要你注意」的東西：輪到你回答的題目、小精靈工作中的卡片、底部操作列、下拉選單與 tooltip。

### Named Rules
**The Your-Turn Lift Rule.** 浮起陰影是一種狀態，不是裝飾。只有輪到使用者行動、或小精靈正在工作的元素才浮起來；其他東西一律貼在桌面上。同一時間只有一題浮起：小精靈正在問的那一題。

## Shapes

圓潤、柔軟。三種圓角：大卡片與浮動列 18px、輸入框／提示／選項 12px、按鈕／徽章／切換鈕全膠囊（999px）。邊線一律 1px 鼠尾草色。狀態靠加粗邊線表達：選中的選項 2px 夜林綠，待確認 Premise 卡片頂端 4px 琥珀線，新版 Spec 2px 琥珀外框。勾選圓點、頭像、`?` 說明鈕都是正圓。

## Components

### Buttons
柔軟、好按的膠囊。
- **Shape:** 全膠囊（999px），內距 7px 16px，14px 字。
- **Primary:** 夜林綠底、白字；hover 時亮度提高 8%。
- **Default:** 白底、鼠尾草邊線、深松墨字；hover 換成鼠尾草淡染底。
- **Link:** 無框無底的夜林綠文字，用於次要動作（修改題目、撤回、登出）。破壞性的 link 改成餘燼紅。
- **Icon:** 36px 正方、透明底、苔蘚色；破壞性 icon 在 hover 時換成餘燼紅加餘燼薄霧。
- **Disabled:** 50% 透明度。
- **Focus:** 全站統一 2px 夜林綠焦點框（offset 2px），跟著元件的圓角走。

### Segmented Control
一條膠囊外框裡並排的按鈕，用於 Role、類型、To、題數、篩選、票種。選中的那格填滿夜林綠、白字，未選中的保持白底。頭尾兩格自己帶半圓角（不用 overflow 裁切），焦點框才不會被切掉；寬度貼合內容，不撐滿整列。

### Answer Options
題目的候選答案，整列寬、左對齊的 12px 圓角按鈕，最小高度 44px。選中時變成 2px 夜林綠邊加夜林薄霧底；AI 推薦的選項帶一個「建議」小膠囊標籤。

### Chips / Badges
- **Style:** 12px 字的膠囊，預設鼠尾草淡染底、苔蘚字、細邊線。
- **Variants:** accent（夜林薄霧底、夜林深綠字）、ok（葉綠）、warn 與 premise（燒糖琥珀）、danger（餘燼紅），都是同色系薄霧底、無邊線；「核心」用深松墨反白；「試用版」用琥珀小字。

### Cards / Containers
- **Corner Style:** 18px。
- **Background:** 白紙；次層區塊（證據、統計、New Term）用鼠尾草淡染加 12px 圓角。
- **Shadow Strategy:** 靜止時用 Rest，輪到你時用 Lift（見 Elevation）。
- **Border:** 1px 鼠尾草邊線；輪到你回答的題目換成夜林綠邊。
- **Internal Padding:** 16px；題目卡 18px 20px，已解決的題目收成 12px 20px。

### Inputs / Fields
- **Style:** 白底、1px 欄位邊線（Field Border，白底上 3.21:1，深色模式 `#5d7565`）、12px 圓角、內距 8px 12px，寬度 100%。標籤在上方，13px 苔蘚色。游標顏色是夜林綠。
- **Focus:** 邊線換成夜林綠，外加 2px 夜林綠焦點框（offset 1px）。
- **File picker:** 原生「選擇檔案」按鈕改成和 Default Button 一樣的膠囊。

### Notices
12px 圓角、10px 14px 內距的色塊，沒有邊框，以語意薄霧色當底（info 夜林薄霧、ok、warn 燒糖琥珀、danger 餘燼紅）。帶小精靈的版本（`with-sprite`）會在左側放一隻 56px 的小精靈。

### Navigation
白底黏頂列，底部一條鼠尾草線。左邊是 28px logo 小精靈加 19px Huninn 品牌字與「試用版」徽章；導覽連結 14px 苔蘚色，目前頁面改成深松墨加 500 字重；右側是 ADO 狀態徽章、使用者名稱與登出 link。

### Sprite（Signature）
螢火蟲小精靈，120×120 的 SVG，深松墨圓頭線條。姿勢：
- **logo**（28px，簡化、粗線）：品牌標誌。
- **head**：登入頁與使用說明。
- **reading**（72px，捧書、身後螢火光暈每 2.4 秒呼吸一次）：AI 工作中。
- **ticket**（56px，拿著一張票、旁邊一顆星）：完成時刻。

深色模式下小精靈加一圈 1px 的淺色光暈（`--sprite-halo`），深松墨的觸角與輪廓才看得見；線條顏色本身不變。

### Thinking Card（Signature）
小精靈工作中時顯示：reading 姿勢的小精靈、標題與已等時間，下方是讀過的檔案路徑（等寬小膠囊，最新那一個用夜林綠標示）。卡片用 Lift 陰影與深邊線浮起來，讓等待看得見。

### Current Question（Signature）
拷問頁唯一的高峰：Requester 下一題要回答的那張卡（每輪 Premise 優先）。
- 小精靈（head 姿勢，52px）從卡片上緣探出頭，進場時往上滑 0.6 秒（ease-out）。
- 2px 夜林綠框加 Lift 陰影；其他待回答的題目只有夜林綠框，不浮起。
- 題目標題 20px，內容 17px；「小精靈建議」放在夜林薄霧底的區塊裡，像小精靈在說話。

### Done Card（Signature）
小精靈認為問完、或題數問滿時出現：ticket 姿勢小精靈（76px）跳一下進場，Huninn 標題「問完了！」，右側直接放「產出 Spec」。這時底部操作列收起，同一個動作只出現一次。2px 夜林綠框、夜林薄霧底、Lift 陰影。

### Stepper & Tally
- **Stepper:** 四格、6px 高的進度條（Request → 拷問 → Spec → ADO 票）。完成的格子填夜林綠；目前那格是螢火黃並發光（進度屬於小精靈，見 The One Lamp Rule），標籤改用 Huninn 16px。
- **Tally:** 側欄三格統計（Answer／Open／Assumption），數字用 Huninn 28px，有數字時改成對應的語意薄霧色。

## Do's and Don'ts

### Do:
- **Do** 所有顏色都透過 `globals.css` 的語意變數取用，深色模式才會跟著切換。
- **Do** 按鈕、徽章、切換鈕維持全膠囊（999px），卡片 18px、內層區塊 12px。
- **Do** 在完成、空狀態、等待這些時刻請小精靈出場（ticket、head、reading 姿勢），文案用親切口語。
- **Do** 只把浮起陰影（Lift）給輪到使用者行動或小精靈正在工作的元素。
- **Do** 有「未確定」的內容時用燒糖琥珀標示，讓 Spec 的虛處一眼可見。

### Don't:
- **Don't** 把螢火黃用在小精靈與進度以外的地方（The One Lamp Rule）。
- **Don't** 把燒糖琥珀當裝飾色（The Amber Means Unsure Rule）。
- **Don't** 加粗 Huninn，也不要拿它排內文（The Round Voice Rule）。
- **Don't** 在卡片上疊多層陰影或加大面積的漸層；層次靠淡綠底色與細邊線。
- **Don't** 加入第二個行動色；夜林綠是桌上唯一的行動色。
