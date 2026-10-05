"""
dashboard.py — Enterprise Real-Time Analytics Web Dashboard.

Al-Razi University | Faculty of Computing & Artificial Intelligence | Big Data Course
Author: Mushtaq Alfaqih | Supervised by: Eng. Omar Abusand

Serves a modern, dark-mode Glassmorphic Single-Page Application (SPA) directly
via FastAPI on /dashboard. Connects dynamically to live API routes:
  - /health
  - /aggregations/sales_by_city
  - /aggregations/orders_by_status
  - /aggregations/sales_by_period
  - /aggregations/top_products
  - /refresh-mv
  - /jobs/pipeline_consistency_audit/run
"""

from __future__ import annotations


def get_dashboard_html() -> str:
    """Returns the standalone HTML/CSS/JS payload for the executive dashboard."""
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Enterprise Big Data Analytics Platform | لوحة التحكم التحليلية</title>
  <meta name="description" content="Live Real-Time Big Data Executive Analytics Dashboard for Hybrid ELT Pipeline">
  
  <!-- Modern Typography from Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
  
  <!-- Chart.js for High-Performance Vector Data Visualization -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

  <style>
    :root {
      --bg-dark: #0b0f19;
      --bg-card: rgba(17, 24, 39, 0.75);
      --bg-card-hover: rgba(31, 41, 55, 0.85);
      --border-card: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(99, 102, 241, 0.3);
      
      --accent-blue: #3b82f6;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-violet: #8b5cf6;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      
      --shadow-glow: 0 0 25px rgba(99, 102, 241, 0.15);
      --radius-sm: 8px;
      --radius-md: 14px;
      --radius-lg: 20px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.12) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.12) 0px, transparent 50%),
        radial-gradient(at 50% 50%, rgba(16, 185, 129, 0.05) 0px, transparent 50%);
      background-attachment: fixed;
      color: var(--text-main);
      font-family: 'Cairo', 'Outfit', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }

    /* Top Navigation Header */
    header {
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-card);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 0.85rem 2rem;
    }

    .nav-container {
      max-width: 1440px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }

    .brand-section {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .brand-logo {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      box-shadow: 0 0 20px rgba(59, 130, 246, 0.4);
    }

    .brand-text h1 {
      font-size: 1.25rem;
      font-weight: 800;
      background: linear-gradient(90deg, #60a5fa, #c084fc, #34d399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.5px;
    }

    .brand-text p {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-family: 'Outfit', sans-serif;
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }

    .nav-btn {
      padding: 0.5rem 1rem;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-card);
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      cursor: pointer;
    }

    .nav-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }

    .nav-btn.primary {
      background: linear-gradient(135deg, #2563eb, #7c3aed);
      border: none;
      color: white;
      box-shadow: 0 0 15px rgba(37, 99, 235, 0.4);
    }

    .nav-btn.primary:hover {
      background: linear-gradient(135deg, #1d4ed8, #6d28d9);
      box-shadow: 0 0 20px rgba(37, 99, 235, 0.6);
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.8rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
      font-family: 'JetBrains Mono', monospace;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* Main Container */
    main {
      flex: 1;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 2rem;
      display: flex;
      flex-direction: column;
      gap: 2rem;
    }

    /* KPI Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
    }

    .kpi-card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: var(--radius-md);
      padding: 1.5rem;
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
    }

    .kpi-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--card-accent, #3b82f6), transparent);
    }

    .kpi-card:hover {
      background: var(--bg-card-hover);
      border-color: var(--border-accent);
      transform: translateY(-3px);
      box-shadow: var(--shadow-glow);
    }

    .kpi-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }

    .kpi-title {
      font-size: 0.9rem;
      color: var(--text-muted);
      font-weight: 600;
    }

    .kpi-icon {
      font-size: 1.4rem;
    }

    .kpi-value {
      font-size: 2.2rem;
      font-weight: 800;
      font-family: 'JetBrains Mono', 'Outfit', monospace;
      color: var(--text-main);
      letter-spacing: -1px;
      line-height: 1.2;
    }

    .kpi-sub {
      font-size: 0.8rem;
      color: var(--text-dim);
      margin-top: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.3rem;
    }

    /* Charts Section */
    .charts-grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 1.5rem;
    }

    .chart-box {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: var(--radius-md);
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .col-7 { grid-column: span 7; }
    .col-5 { grid-column: span 5; }
    .col-6 { grid-column: span 6; }
    .col-12 { grid-column: span 12; }

    @media (max-width: 1024px) {
      .col-7, .col-5, .col-6 { grid-column: span 12; }
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      padding-bottom: 0.75rem;
    }

    .chart-title {
      font-size: 1.05rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .chart-tag {
      font-size: 0.75rem;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      background: rgba(59, 130, 246, 0.15);
      color: #60a5fa;
      font-family: 'JetBrains Mono', monospace;
    }

    .chart-canvas-container {
      position: relative;
      flex: 1;
      min-height: 280px;
    }

    /* Live Action Banner */
    .action-banner {
      background: linear-gradient(135deg, rgba(30, 58, 138, 0.4), rgba(88, 28, 135, 0.4));
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: var(--radius-md);
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }

    .action-text h3 {
      font-size: 1.1rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
    }

    .action-text p {
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .action-btns {
      display: flex;
      gap: 0.75rem;
    }

    /* Toast Notification */
    #toast {
      position: fixed;
      bottom: 2rem;
      left: 2rem;
      background: rgba(17, 24, 39, 0.95);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(59, 130, 246, 0.4);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      color: var(--text-main);
      padding: 1rem 1.5rem;
      border-radius: var(--radius-md);
      font-size: 0.9rem;
      display: none;
      align-items: center;
      gap: 0.75rem;
      z-index: 1000;
      animation: slideUp 0.3s ease;
      direction: rtl;
    }

    @keyframes slideUp {
      from { transform: translateY(100%); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    /* Footer */
    footer {
      border-top: 1px solid var(--border-card);
      padding: 1.5rem 2rem;
      background: rgba(11, 15, 25, 0.9);
      font-size: 0.85rem;
      color: var(--text-muted);
      text-align: center;
      margin-top: auto;
    }

    footer b {
      color: var(--text-main);
    }

    /* Skeleton Loader */
    .skeleton {
      background: linear-gradient(90deg, rgba(255,255,255,0.05) 25%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.05) 75%);
      background-size: 200% 100%;
      animation: skeleton-loading 1.5s infinite;
      border-radius: 4px;
      display: inline-block;
      min-width: 80px;
      min-height: 1.5rem;
    }

    @keyframes skeleton-loading {
      0% { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header>
    <div class="nav-container">
      <div class="brand-section">
        <div class="brand-logo">⚡</div>
        <div class="brand-text">
          <h1>منصة البيانات الضخمة والتحليلات الحية</h1>
          <p>Enterprise Hybrid ELT Pipeline & Analytical Platform</p>
        </div>
      </div>
      
      <div class="nav-links">
        <span class="status-pill" id="system-status-pill">
          <span class="status-dot"></span>
          <span id="system-status-text">النظام متصل ونشط</span>
        </span>
        <button class="nav-btn primary" id="btn-refresh-mv" onclick="triggerRefreshMV()">
          🔄 تحديث الجداول المادية
        </button>
        <button class="nav-btn" id="btn-run-audit" onclick="triggerAuditJob()">
          🛡️ فحص التماسك الرياضي
        </button>
        <a href="/docs" target="_blank" class="nav-btn" id="btn-swagger-docs">
          ⚡ Swagger UI (/docs)
        </a>
        <a href="https://github.com/mushtaqalfaqih/BigData-Midterm-Pipeline" target="_blank" class="nav-btn">
          📂 مستودع GitHub
        </a>
      </div>
    </div>
  </header>

  <!-- Main Content -->
  <main>

    <!-- Top Action Banner -->
    <div class="action-banner">
      <div class="action-text">
        <h3>🎯 لوحة مؤشرات الأداء الحية (Live Real-Time Data Pipeline Telemetry)</h3>
        <p>مربوطة مباشرة بقواعد بيانات MongoDB ومحرك التجميعات الإحصائية والجداول المادية التزايدية.</p>
      </div>
      <div class="action-btns">
        <span class="status-pill" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3);">
          ⚡ معادلة التماسك: Raw == Valid + Corr + Quar (Diff: 0)
        </span>
      </div>
    </div>

    <!-- KPI Row -->
    <section class="kpi-grid">
      <div class="kpi-card" style="--card-accent: #3b82f6;">
        <div class="kpi-header">
          <span class="kpi-title">إجمالي السجلات الخام (Raw Fidelity)</span>
          <span class="kpi-icon">📥</span>
        </div>
        <div class="kpi-value" id="count-raw"><span class="skeleton"></span></div>
        <div class="kpi-sub">🗄️ orders_raw • حفظ كامل المصدر دون أي تعديل</div>
      </div>

      <div class="kpi-card" style="--card-accent: #10b981;">
        <div class="kpi-header">
          <span class="kpi-title">السجلات النظيفة المصنفة (Clean Data)</span>
          <span class="kpi-icon">✅</span>
        </div>
        <div class="kpi-value" id="count-validated"><span class="skeleton"></span></div>
        <div class="kpi-sub">🔒 orders_validated • مفهرسة بـ order_id فريد</div>
      </div>

      <div class="kpi-card" style="--card-accent: #f43f5e;">
        <div class="kpi-header">
          <span class="kpi-title">سجلات الحجر الصحي (Quarantined)</span>
          <span class="kpi-icon">⛔</span>
        </div>
        <div class="kpi-value" id="count-quarantine"><span class="skeleton"></span></div>
        <div class="kpi-sub">🛡️ orders_quarantine • أخطاء مدققة بأكواد حتمية</div>
      </div>

      <div class="kpi-card" style="--card-accent: #8b5cf6;">
        <div class="kpi-header">
          <span class="kpi-title">عناصر الطلبات المسطحة (Line Items)</span>
          <span class="kpi-icon">📦</span>
        </div>
        <div class="kpi-value" id="count-items-flat"><span class="skeleton"></span></div>
        <div class="kpi-sub">📑 order_items_flat • تسريع استعلامات المنتجات</div>
      </div>

      <div class="kpi-card" style="--card-accent: #f59e0b;">
        <div class="kpi-header">
          <span class="kpi-title">المهام المجدولة وسجل التدقيق</span>
          <span class="kpi-icon">⏰</span>
        </div>
        <div class="kpi-value" id="count-jobs"><span class="skeleton"></span></div>
        <div class="kpi-sub">⏱️ job_runs • توثيق كل عملية تشغيل بالمللي ثانية</div>
      </div>
    </section>

    <!-- Charts Row 1 -->
    <section class="charts-grid">
      <!-- Sales by City Chart -->
      <div class="chart-box col-7">
        <div class="chart-header">
          <span class="chart-title">🏙️ إجمالي الإيرادات وعدد الطلبات حسب المدينة</span>
          <span class="chart-tag">GET /aggregations/sales_by_city</span>
        </div>
        <div class="chart-canvas-container">
          <canvas id="chart-city"></canvas>
        </div>
      </div>

      <!-- Status Breakdown Chart -->
      <div class="chart-box col-5">
        <div class="chart-header">
          <span class="chart-title">🍩 توزيع حالات الطلبات التشغيلية</span>
          <span class="chart-tag">GET /aggregations/orders_by_status</span>
        </div>
        <div class="chart-canvas-container">
          <canvas id="chart-status"></canvas>
        </div>
      </div>
    </section>

    <!-- Charts Row 2 -->
    <section class="charts-grid">
      <!-- Sales Trend Line Chart -->
      <div class="chart-box col-6">
        <div class="chart-header">
          <span class="chart-title">📈 حركة الإيرادات اليومية وتدفق المبيعات</span>
          <span class="chart-tag">GET /aggregations/sales_by_period</span>
        </div>
        <div class="chart-canvas-container">
          <canvas id="chart-period"></canvas>
        </div>
      </div>

      <!-- Top Products Bar Chart -->
      <div class="chart-box col-6">
        <div class="chart-header">
          <span class="chart-title">🏆 المنتجات الأكثر مبيعاً وإيراداً</span>
          <span class="chart-tag">GET /aggregations/top_products</span>
        </div>
        <div class="chart-canvas-container">
          <canvas id="chart-products"></canvas>
        </div>
      </div>
    </section>

  </main>

  <!-- Live Toast Notification Container -->
  <div id="toast"></div>

  <!-- Footer -->
  <footer>
    <p>
      جامعة الرازي | كلية الحاسوب والذكاء الاصطناعي | مقرر البيانات الضخمة (Big Data Course)  
      <br>
      مهندس ومطور المشروع: <b>مشتاق الفقيه (Mushtaq Alfaqih)</b> | إشراف: <b>م. عمر أبوسند (Eng. Omar Abusand)</b>
    </p>
  </footer>

  <!-- Application Logic & Live Data Fetching -->
  <script>
    let cityChart, statusChart, periodChart, productsChart;

    function showToast(msg, isSuccess = true) {
      const toast = document.getElementById('toast');
      toast.style.borderColor = isSuccess ? 'rgba(16, 185, 129, 0.6)' : 'rgba(244, 63, 94, 0.6)';
      toast.innerHTML = (isSuccess ? '✅ ' : '❌ ') + msg;
      toast.style.display = 'flex';
      setTimeout(() => { toast.style.display = 'none'; }, 4000);
    }

    // Format currency numbers nicely
    function formatNumber(num) {
      if (num === null || num === undefined) return '0';
      return Number(num).toLocaleString('ar-YE');
    }

    // Load Live KPI Metrics
    async function loadHealthMetrics() {
      try {
        const res = await fetch('/health');
        if (!res.ok) throw new Error('Health check failed');
        const data = await res.json();
        
        const counts = data.database?.counts || {};
        document.getElementById('count-raw').innerText = formatNumber(counts.orders_raw);
        document.getElementById('count-validated').innerText = formatNumber(counts.orders_validated);
        document.getElementById('count-quarantine').innerText = formatNumber(counts.orders_quarantine);
        document.getElementById('count-items-flat').innerText = formatNumber(counts.order_items_flat);
        document.getElementById('count-jobs').innerText = formatNumber(counts.job_runs);

        const statusPill = document.getElementById('system-status-text');
        if (data.database?.status === 'CONNECTED') {
          statusPill.innerText = 'متصل بقاعدة البيانات (' + data.database.name + ')';
        } else {
          statusPill.innerText = 'تنبيه: قاعدة البيانات غير متصلة';
        }
      } catch (err) {
        console.error('Failed loading health metrics:', err);
      }
    }

    // Load Sales by City Chart
    async function loadCityChart() {
      try {
        const res = await fetch('/aggregations/sales_by_city?limit=8');
        const data = await res.json();
        const results = data.results || [];

        const labels = results.map(r => r.city || 'غير محدد');
        const revenues = results.map(r => (r.total_revenue || 0) / 1000000); // In Millions
        const orderCounts = results.map(r => r.order_count || 0);

        const ctx = document.getElementById('chart-city').getContext('2d');
        if (cityChart) cityChart.destroy();

        cityChart = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'الإيرادات (مليون ريال)',
                data: revenues,
                backgroundColor: 'rgba(59, 130, 246, 0.75)',
                borderColor: '#3b82f6',
                borderWidth: 1,
                borderRadius: 6,
                yAxisID: 'y'
              },
              {
                label: 'عدد الطلبات',
                data: orderCounts,
                backgroundColor: 'rgba(16, 185, 129, 0.75)',
                borderColor: '#10b981',
                borderWidth: 1,
                borderRadius: 6,
                yAxisID: 'y1'
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: { labels: { color: '#9ca3af', font: { family: 'Cairo' } } },
              tooltip: { rtl: true }
            },
            scales: {
              x: { ticks: { color: '#9ca3af', font: { family: 'Cairo' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
              y: { type: 'linear', display: true, position: 'left', ticks: { color: '#60a5fa' }, grid: { color: 'rgba(255,255,255,0.05)' } },
              y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#34d399' } }
            }
          }
        });
      } catch (err) {
        console.error('Failed loading city chart:', err);
      }
    }

    // Load Order Status Distribution Chart
    async function loadStatusChart() {
      try {
        const res = await fetch('/aggregations/orders_by_status');
        const data = await res.json();
        const results = data.results || [];

        // Aggregate by status label
        const statusMap = {};
        results.forEach(r => {
          const s = r.status || 'أخرى';
          statusMap[s] = (statusMap[s] || 0) + (r.order_count || 0);
        });

        const labels = Object.keys(statusMap);
        const values = Object.values(statusMap);

        const ctx = document.getElementById('chart-status').getContext('2d');
        if (statusChart) statusChart.destroy();

        statusChart = new Chart(ctx, {
          type: 'doughnut',
          data: {
            labels: labels,
            datasets: [{
              data: values,
              backgroundColor: [
                'rgba(16, 185, 129, 0.8)',
                'rgba(59, 130, 246, 0.8)',
                'rgba(245, 158, 11, 0.8)',
                'rgba(244, 63, 94, 0.8)',
                'rgba(139, 92, 246, 0.8)'
              ],
              borderColor: '#0b0f19',
              borderWidth: 2
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { color: '#9ca3af', font: { family: 'Cairo' } } },
              tooltip: { rtl: true }
            }
          }
        });
      } catch (err) {
        console.error('Failed loading status chart:', err);
      }
    }

    // Load Daily Sales Velocity Chart
    async function loadPeriodChart() {
      try {
        const res = await fetch('/aggregations/sales_by_period?limit=12');
        const data = await res.json();
        const results = (data.results || []).reverse();

        const labels = results.map(r => r.day || r.date || '');
        const amounts = results.map(r => (r.total_sales || r.total_revenue || 0) / 1000000);

        const ctx = document.getElementById('chart-period').getContext('2d');
        if (periodChart) periodChart.destroy();

        periodChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [{
              label: 'مبيعات الأيام (مليون ريال)',
              data: amounts,
              borderColor: '#c084fc',
              backgroundColor: 'rgba(192, 132, 252, 0.15)',
              fill: true,
              tension: 0.35,
              pointBackgroundColor: '#c084fc',
              pointRadius: 4
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: '#9ca3af', font: { family: 'Cairo' } } },
              tooltip: { rtl: true }
            },
            scales: {
              x: { ticks: { color: '#9ca3af', font: { family: 'Cairo' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
              y: { ticks: { color: '#c084fc' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
          }
        });
      } catch (err) {
        console.error('Failed loading period chart:', err);
      }
    }

    // Load Top Products Chart
    async function loadProductsChart() {
      try {
        const res = await fetch('/aggregations/top_products?limit=5');
        const data = await res.json();
        const results = data.results || [];

        const labels = results.map(r => (r.product_name || r.sku || '').substring(0, 20));
        const revenues = results.map(r => (r.total_revenue || 0) / 1000000);

        const ctx = document.getElementById('chart-products').getContext('2d');
        if (productsChart) productsChart.destroy();

        productsChart = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'الإيرادات (مليون ريال)',
              data: revenues,
              backgroundColor: 'rgba(245, 158, 11, 0.75)',
              borderColor: '#f59e0b',
              borderWidth: 1,
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: '#9ca3af', font: { family: 'Cairo' } } },
              tooltip: { rtl: true }
            },
            scales: {
              x: { ticks: { color: '#f59e0b' }, grid: { color: 'rgba(255,255,255,0.05)' } },
              y: { ticks: { color: '#9ca3af', font: { family: 'Cairo' } }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
          }
        });
      } catch (err) {
        console.error('Failed loading products chart:', err);
      }
    }

    // Trigger Materialized Views Refresh
    async function triggerRefreshMV() {
      const btn = document.getElementById('btn-refresh-mv');
      btn.disabled = true;
      btn.innerText = '⏳ جاري التحديث...';
      try {
        const res = await fetch('/refresh-mv?full=false', { method: 'POST' });
        const data = await res.json();
        showToast(`تم التحديث بنجاح خلال ${data.elapsed_ms || 0} مللي ثانية! (الحالة: ${data.status})`);
        await refreshAllData();
      } catch (err) {
        showToast('فشل في استدعاء التحديث: ' + err, false);
      } finally {
        btn.disabled = false;
        btn.innerText = '🔄 تحديث الجداول المادية';
      }
    }

    // Trigger Consistency Audit Job
    async function triggerAuditJob() {
      const btn = document.getElementById('btn-run-audit');
      btn.disabled = true;
      btn.innerText = '⏳ جاري الفحص...';
      try {
        const res = await fetch('/jobs/pipeline_consistency_audit/run', { method: 'POST' });
        const data = await res.json();
        const details = data.execution?.details || {};
        showToast(`فحص التماسك الرياضي: ${details.audit_passed ? 'ناجح بنسبة 100% (Diff: 0)' : 'تم اكتشاف فروقات'}!`);
        await loadHealthMetrics();
      } catch (err) {
        showToast('فشل تشغيل مهمة التدقيق: ' + err, false);
      } finally {
        btn.disabled = false;
        btn.innerText = '🛡️ فحص التماسك الرياضي';
      }
    }

    // Reload all charts and counters
    async function refreshAllData() {
      await Promise.all([
        loadHealthMetrics(),
        loadCityChart(),
        loadStatusChart(),
        loadPeriodChart(),
        loadProductsChart()
      ]);
    }

    // Initialize Dashboard on Page Load
    window.addEventListener('DOMContentLoaded', () => {
      refreshAllData();
    });
  </script>
</body>
</html>
"""
