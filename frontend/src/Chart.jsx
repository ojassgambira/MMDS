import React, { useEffect, useRef, useState } from "react";
let library;
const plotly = () =>
  (library ??= import("plotly.js-cartesian-dist-min").then(
    (module) => module.default,
  ));
export default function Chart({ label, data, layout = {}, onClick }) {
  const target = useRef(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let alive = true,
      resize,
      instance;
    plotly()
      .then(async (Plotly) => {
        if (!alive) return;
        instance = Plotly;
        await Plotly.react(
          target.current,
          data,
          {
            autosize: true,
            height: 340,
            paper_bgcolor: "transparent",
            plot_bgcolor: "transparent",
            font: {
              family: "system-ui, sans-serif",
              color: "#223842",
              size: 12,
            },
            colorway: [
              "#087f8c",
              "#db9c34",
              "#6079a4",
              "#925c83",
              "#53865d",
              "#ba695b",
              "#799f9b",
              "#566273",
            ],
            margin: { l: 58, r: 18, t: 18, b: 55 },
            xaxis: { gridcolor: "#e9eeed", zeroline: false },
            yaxis: { gridcolor: "#e9eeed", zeroline: false },
            legend: { orientation: "h", y: -0.2 },
            ...layout,
          },
          {
            responsive: true,
            displaylogo: false,
            scrollZoom: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
          },
        );
        if (!alive) return;
        if (onClick) target.current.on("plotly_click", onClick);
        resize = new ResizeObserver(() => {
          if (alive && target.current) Plotly.Plots.resize(target.current);
        });
        resize.observe(target.current);
      })
      .catch((error) => {
        if (alive) setError(error.message);
      });
    const node = target.current;
    return () => {
      alive = false;
      resize?.disconnect();
      if (instance && node) instance.purge(node);
    };
  }, [data, layout, onClick]);
  if (error) return <p role="alert">Chart could not render: {error}</p>;
  return (
    <div className="chart" role="figure" aria-label={label} ref={target} />
  );
}
