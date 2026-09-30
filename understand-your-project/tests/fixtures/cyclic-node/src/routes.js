const express = require("express");
const handlers = require("./handlers");

const router = express.Router();
router.get("/", handlers.home);
module.exports = router;
