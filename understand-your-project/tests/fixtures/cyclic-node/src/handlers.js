const routes = require("./routes");

function home(req, res) {
  res.send("home");
}
module.exports = { home, routes };
