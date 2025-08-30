(function () {
  const KEY = "theme";
  const root = document.documentElement;
  function apply(theme) {
    if (theme === "dark") root.setAttribute("data-theme", "dark");
    else root.removeAttribute("data-theme");
  }
  const saved = localStorage.getItem(KEY);
  if (saved) apply(saved);
  window.toggleTheme = function () {
    const isDark = root.getAttribute("data-theme") === "dark";
    const next = isDark ? "light" : "dark";
    localStorage.setItem(KEY, next);
    apply(next);
  };
})();
