import type React from 'react';
import styles from './CodeViewer.module.css';

/* ── Token factory ── */
const token = (cls: string) =>
  function Token({ t }: { t: string }) { return <span className={cls}>{t}</span>; };

const Cmt = token(styles.cmt);
const Dec = token(styles.dec);
const Kw  = token(styles.kw);
const Fn  = token(styles.fn);
const Ty  = token(styles.ty);
const Str = token(styles.str);
const Doc = token(styles.doc);
const Op  = token(styles.op);
const Va  = token(styles.va);

interface LineProps { n: number; children?: React.ReactNode }
const L = ({ n, children }: LineProps) => (
  <div className={styles.line}>
    <span className={styles.ln}>{String(n).padStart(2, '\u00a0')}</span>
    <span className={styles.lc}>{children ?? '\u00a0'}</span>
  </div>
);

export default function CodeViewer() {
  return (
    <div className={styles.panel}>
      {/* ── Header ── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.fileIcon}>⬡</span>
          <span className={styles.filename}>agent<span className={styles.sep}></span></span>
        </div>
        <span className={styles.badge}>READ ONLY</span>
      </div>

      {/* ── Code body ── */}
      <div className={styles.body}>
        {/* CRT scanline overlay */}
        <div className={styles.scanline} aria-hidden />

        <div className={styles.code}>
          <L n={1}><Cmt t="# ========== Tool 1: Get Weather ==========" /></L>
          <L n={2}><Dec t="@function_tool" /></L>
          <L n={3}>
            <Kw t="def " /><Fn t="get_weather" /><Op t="(" />
            <Va t="city" /><Op t=": " /><Ty t="Annotated" /><Op t="[" />
            <Ty t="str" /><Op t=", " /><Str t='"The city to get weather for"' />
            <Op t="]) -&gt; " /><Ty t="str" /><Op t=":" />
          </L>
          <L n={4}>
            <span className={styles.indent} />
            <Doc t='"""Get the current weather for a specified city."""' />
          </L>
          <L n={5} />
          <L n={6}><Cmt t="# ========== Tool 2: Get Clothing Advice ==========" /></L>
          <L n={7}><Dec t="@function_tool" /></L>
          <L n={8}>
            <Kw t="def " /><Fn t="get_clothing_advice" /><Op t="(" />
            <Va t="weather" /><Op t=": " /><Ty t="Annotated" /><Op t="[" />
            <Ty t="str" /><Op t=", " /><Str t='"The weather description"' />
            <Op t="]) -&gt; " /><Ty t="str" /><Op t=":" />
          </L>
          <L n={9}>
            <span className={styles.indent} />
            <Doc t='"""Give clothing advice based on weather conditions."""' />
          </L>
          <L n={10} />
          <L n={11} />
          <L n={12}><Cmt t="# ========== Tool 3: Translate Text ==========" /></L>
          <L n={13}><Dec t="@function_tool" /></L>
          <L n={14}>
            <Kw t="def " /><Fn t="translate_text" /><Op t="(" />
            <Va t="text" /><Op t=": " /><Ty t="Annotated" /><Op t="[" />
            <Ty t="str" /><Op t=", " /><Str t='"The text to translate"' />
            <Op t="], " />
            <Va t="target_language" /><Op t=": " /><Ty t="Annotated" /><Op t="[" />
            <Ty t="str" /><Op t=", " /><Str t='"Target language code, e.g. en, ja, fr"' />
            <Op t="]) -&gt; " /><Ty t="str" /><Op t=":" />
          </L>
          <L n={15}>
            <span className={styles.indent} />
            <Doc t='"""Translate text to the specified language."""' />
          </L>
          <L n={16} />
          <L n={17}><Cmt t="# ========== Tool 4: Text Statistics ==========" /></L>
          <L n={18}><Dec t="@function_tool" /></L>
          <L n={19}>
            <Kw t="def " /><Fn t="text_statistics" /><Op t="(" />
            <Va t="text" /><Op t=": " /><Ty t="Annotated" /><Op t="[" />
            <Ty t="str" /><Op t=", " /><Str t='"The text to analyze"' />
            <Op t="]) -&gt; " /><Ty t="str" /><Op t=":" />
          </L>
          <L n={20}>
            <span className={styles.indent} />
            <Doc t='"""Analyze text and return statistics like character count and word count."""' />
          </L>
          <L n={21} />
          <L n={22}><Cmt t="# ========== Agent ==========" /></L>
          <L n={23}>
            <Va t="agent" /><Op t=" = " /><Ty t="Agent" /><Op t="(" />
          </L>
          <L n={24}>
            <span className={styles.indent} />
            <Va t="name" /><Op t="=" /><Str t='"Assistant"' /><Op t="," />
          </L>
          <L n={25}>
            <span className={styles.indent} />
            <Va t="instructions" /><Op t="=" />
            <Str t='"You are a helpful assistant. Use the available tools to answer questions."' />
            <Op t="," />
          </L>
          <L n={26}>
            <span className={styles.indent} />
            <Va t="tools" /><Op t="=[" />
            <Fn t="get_weather" /><Op t=", " />
            <Fn t="get_clothing_advice" /><Op t=", " />
            <Fn t="translate_text" /><Op t=", " />
            <Fn t="text_statistics" />
            <Op t="]," />
          </L>
          <L n={27}>
            <span className={styles.indent} />
            <Va t="model" /><Op t="=" /><Va t="llm_model" /><Op t="," />
          </L>
          <L n={28}><Op t=")" /></L>
        </div>
      </div>

      {/* ── Footer tag ── */}
      <div className={styles.footer}>
        <span className={styles.footerDot} />
        <span>OpenAI Agents SDK · Agent Template</span>
      </div>
    </div>
  );
}
