export default {
  base: "/MMDS/",
  build: { target: "es2022", chunkSizeWarningLimit: 1800 },
  test: { include: ["tests/*.test.js"] },
};
