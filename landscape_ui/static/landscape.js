(() => {
  const source = document.getElementById("landscape-chart-data");
  if (!source || typeof Chart === "undefined") return;
  const data = JSON.parse(source.textContent);
  Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
  Chart.defaults.color = "#506070";
  const colors = ["#176b71", "#305d9b", "#d0a047", "#6c8395", "#b16c6b", "#9ebbc0", "#aaa9c0"];
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const wrapLabel = label => {
    const lines = [];
    let line = "";
    for (const word of label.split(" ")) {
      if (line && `${line} ${word}`.length > 22) {
        lines.push(line);
        line = word;
      } else line = line ? `${line} ${word}` : word;
    }
    if (line) lines.push(line);
    return lines;
  };
  const make = (id, key, doughnut) => {
    const element = document.getElementById(id);
    const rows = data[key];
    if (!element || !rows || !rows.some(row => row.count > 0)) {
      if (element) {
        const note = document.createElement("p");
        note.className = "chart-empty";
        note.textContent = "No trial data for this distribution.";
        element.parentElement.replaceChildren(note);
      }
      return;
    }
    new Chart(element, {
      type: doughnut ? "doughnut" : "bar",
      data: {
        labels: rows.map(row => row.label),
        datasets: [{label: "Trials", data: rows.map(row => row.count),
          backgroundColor: doughnut ? rows.map((_, i) => colors[i % colors.length]) : "#176b71",
          borderWidth: 0, borderRadius: doughnut ? 0 : 3, maxBarThickness: 22}]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: prefersReducedMotion ? false : {duration: 350},
        indexAxis: doughnut ? "x" : "y", cutout: doughnut ? "66%" : undefined,
        plugins: {
          legend: {display: doughnut, position: "bottom", labels: {boxWidth: 10, padding: 14}},
          tooltip: {callbacks: {label: context => `${Number(context.raw).toLocaleString()} trials — select to view evidence`}}
        },
        scales: doughnut ? {} : {
          x: {beginAtZero: true, ticks: {precision: 0}, grid: {color: "#edf1f2"}, border: {display: false}},
          y: {grid: {display: false}, border: {display: false}, ticks: {
            font: {size: 11},
            callback: ["mechanism", "modality", "target"].includes(key)
              ? function(value) { return wrapLabel(this.getLabelForValue(value)); }
              : undefined
          }}
        },
        onClick: (_event, elements) => {
          if (elements.length) window.location.assign(rows[elements[0].index].url);
        },
        onHover: (event, elements) => {
          if (event.native?.target) event.native.target.style.cursor = elements.length ? "pointer" : "default";
        }
      }
    });
  };
  make("study-chart", "study_type", true);
  make("status-chart", "status", false);
  make("phase-chart", "phase", false);
  make("mechanism-chart", "mechanism", false);
  make("modality-chart", "modality", false);
  make("target-chart", "target", false);
})();
