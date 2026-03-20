<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

<a href="https://trendshift.io/repositories/16144" target="_blank"><img src="https://trendshift.io/api/badge/repositories/16144" alt="666ghj%2FMiroFish | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

A Simple and Universal Swarm Intelligence Engine, Predicting Anything
</br>

<a href="https://www.shanda.com/" target="_blank"><img src="./static/image/shanda_logo.png" alt="666ghj%2MiroFish | Shanda" height="40"/></a>

[![GitHub Stars](https://img.shields.io/github/stars/666ghj/MiroFish?style=flat-square&color=DAA520)](https://github.com/666ghj/MiroFish/stargazers)
[![GitHub Watchers](https://img.shields.io/github/watchers/666ghj/MiroFish?style=flat-square)](https://github.com/666ghj/MiroFish/watchers)
[![GitHub Forks](https://img.shields.io/github/forks/666ghj/MiroFish?style=flat-square)](https://github.com/666ghj/MiroFish/network)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/666ghj/MiroFish)

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1469200078932545606/1469201282077163739)
[![X](https://img.shields.io/badge/X-Follow-000000?style=flat-square&logo=x&logoColor=white)](https://x.com/mirofish_ai)
[![Instagram](https://img.shields.io/badge/Instagram-Follow-E4405F?style=flat-square&logo=instagram&logoColor=white)](https://www.instagram.com/mirofish_ai/)



</div>

## ⚡ Project Overview

**MiroFish** is a next-generation AI prediction engine based on multi-agent technology. By extracting seed information from the real world (such as breaking news, policy drafts, financial signals), it automatically constructs a high-fidelity parallel digital world. Within this space, thousands of autonomous agents with independent personalities, long-term memory, and behavioral logic engage in free interaction and social evolution. You can dynamically inject variables through a "god's perspective" to precisely predict future outcomes — **allowing the future to be simulated in a digital sandbox, and decisions to succeed after thousands of battle simulations**.

> All you need to do: Upload seed materials (data analysis reports or interesting stories) and describe your prediction requirements in natural language</br>
> MiroFish will return: A detailed prediction report and a highly interactive digital world for deep exploration

### Our Vision

MiroFish is dedicated to building a swarm intelligence mirror that maps reality, capturing collective emergence driven by individual interactions to transcend traditional prediction limitations:

- **At the Macro Level**: We are a simulation laboratory for decision-makers, allowing policies and PR strategies to be tested at zero risk
- **At the Micro Level**: We are a creative sandbox for individual users, where whether exploring story endings or exploring creative ideas, everything is fun, engaging, and accessible

From serious predictions to entertaining simulations, we make every "what-if" visible and make predicting anything possible.

## 🌐 Live Demo

Welcome to our online demo environment to experience a simulation and prediction about trending public opinion events: [mirofish-live-demo](https://666ghj.github.io/mirofish-demo/)

## 📸 System Screenshots

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/screenshot1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/screenshot2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/screenshot3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/screenshot4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/screenshot5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/screenshot6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

## 🎬 Demo Videos

### 1. Wuhan University Public Opinion Simulation Prediction + MiroFish Project Explanation

<div align="center">
<a href="https://www.bilibili.com/video/BV1VYBsBHEMY/" target="_blank"><img src="./static/image/wuhan_university_demo_cover.png" alt="MiroFish Demo Video" width="75%"/></a>

Click the image to view the complete demo video using the MicroOpinion BettaFish generated "Wuhan University Public Opinion Report" for prediction
</div>

### 2. Dream of the Red Chamber - Lost Ending Prediction Simulation

<div align="center">
<a href="https://www.bilibili.com/video/BV1cPk3BBExq" target="_blank"><img src="./static/image/dream_red_chamber_demo_cover.jpg" alt="MiroFish Demo Video" width="75%"/></a>

Click the image to view the complete demo video based on the first 80 chapters of Dream of the Red Chamber (hundreds of thousands of words), MiroFish's deep prediction of the lost ending
</div>

> Examples of **Financial Trend Prediction Simulation**, **Current Events Prediction Simulation**, and more are coming soon...

## 🔄 Workflow

1. **Graph Construction**: Real-world seed extraction & individual and collective memory injection & GraphRAG construction
2. **Environment Setup**: Entity relationship extraction & character profile generation & environmental configuration agent parameter injection
3. **Start Simulation**: Dual-platform parallel simulation & automatic prediction requirement parsing & dynamic time-series memory updates
4. **Report Generation**: ReportAgent possesses rich tool sets for deep interaction with the post-simulation environment
5. **Deep Interaction**: Converse with any individual in the simulated world & converse with the ReportAgent

## 🚀 Quick Start

### Option 1: Source Code Deployment (Recommended)

#### Prerequisites

| Tool | Version Required | Description | Check Installation |
|------|---------|------|---------|
| **Node.js** | 18+ | Frontend runtime environment, includes npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | Backend runtime environment | `python --version` |
| **uv** | Latest | Python package manager | `uv --version` |

#### 1. Configure Environment Variables

```bash
# Copy example configuration file
cp .env.example .env

# Edit the .env file and fill in necessary API keys
```

**Required environment variables:**

```env
# LLM API configuration (supports any LLM API in OpenAI SDK format)
# Recommended: Use Aliyun Bailian qwen-plus model: https://bailian.console.aliyun.com/
# Note: Consumption is significant, try simulations with less than 40 rounds first
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# Zep Cloud configuration
# Free monthly quota is sufficient for basic usage: https://app.getzep.com/
ZEP_API_KEY=your_zep_api_key
```

#### 2. Install Dependencies

```bash
# One-command installation of all dependencies (root + frontend + backend)
npm run setup:all
```

Or install step by step:

```bash
# Install Node dependencies (root + frontend)
npm run setup

# Install Python dependencies (backend, automatically creates virtual environment)
npm run setup:backend
```

#### 3. Start Services

```bash
# Start both frontend and backend simultaneously (execute in project root)
npm run dev
```

**Service addresses:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

**Start individually:**

```bash
npm run backend   # Start backend only
npm run frontend  # Start frontend only
```

### Option 2: Docker Deployment

```bash
# 1. Configure environment variables (same as source code deployment)
cp .env.example .env

# 2. Pull image and start
docker compose up -d
```

By default, it reads `.env` from the root directory and maps ports `3000 (frontend) / 5001 (backend)`

> Accelerated mirror addresses are already provided as comments in `docker-compose.yml`, replace as needed

## 📬 More Communication

<div align="center">
<img src="./static/image/qq_group.png" alt="QQ Discussion Group" width="60%"/>
</div>

&nbsp;

The MiroFish team is recruiting full-time and intern positions. If you're interested in multi-agent applications, we welcome your resume at: **mirofish@shanda.com**

## 📄 Acknowledgments

**MiroFish is strategically supported and incubated by Shanda Group!**

The MiroFish simulation engine is powered by **[OASIS](https://github.com/camel-ai/oasis)**. We sincerely thank the CAMEL-AI team for their open-source contributions!

## 📈 项目统计

<a href="https://www.star-history.com/#666ghj/MiroFish&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=666ghj/MiroFish&type=date&legend=top-left" />
 </picture>
</a>
