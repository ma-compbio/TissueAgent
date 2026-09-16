const routes = ["overview", "biofigbench-spatial"];

function currentRoute() {
  const route = window.location.hash.replace(/^#\/?/, "").split("/")[0];
  return routes.includes(route) ? route : "overview";
}

function renderRoute() {
  const route = currentRoute();

  document.querySelectorAll("[data-route-page]").forEach((page) => {
    page.classList.toggle("is-active", page.dataset.routePage === route);
  });

  document.querySelectorAll("[data-route-link]").forEach((link) => {
    const active = link.dataset.routeLink === route;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });

  const footer = document.querySelector("[data-overview-footer]");
  if (footer) footer.hidden = route !== "overview";
  document.body.classList.toggle("route-placeholder", route !== "overview");
  document.title = route === "overview"
    ? "TissueAgent · Reproducible spatial analysis"
    : "BioFigBench–Spatial · TissueAgent";

  window.scrollTo({ top: 0, behavior: "auto" });
  requestAnimationFrame(observeReveals);
}

let revealObserver;

function observeReveals() {
  if (revealObserver) revealObserver.disconnect();

  revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.12 },
  );

  document.querySelectorAll(".page.is-active .reveal:not(.is-visible)").forEach((el) => {
    revealObserver.observe(el);
  });
}

document.querySelectorAll(".placeholder-link").forEach((link) => {
  link.addEventListener("click", (event) => event.preventDefault());
});

document.querySelectorAll("[data-scroll-target]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const target = document.getElementById(link.dataset.scrollTarget);
    target?.scrollIntoView({ behavior: "smooth" });
  });
});

window.addEventListener("hashchange", renderRoute);
renderRoute();
