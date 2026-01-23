const express = require('express');
const path = require('path');
const fs = require('fs');
const app = express();
const port = process.env.LAB_CONSOLE_PORT || 4200;
const restPort = process.env.LABCONSOLE_SERVER_REST_PORT || 9000;

const indexHtmlPath = path.join(__dirname, 'public', 'index.html');
let indexHtml = '';
try {
  indexHtml = fs.readFileSync(indexHtmlPath, 'utf8');
} catch (err) {
  console.error('Could not read index.html!', err);
  process.exit(1);
}

app.use(express.static(path.join(__dirname, 'public')));


app.get('/*', function(req,res) {
  // append the init data
  const script = `
<script type="application/json" id="app-data">
  {
    "overrideLabConsoleServerUrl": "${req.protocol}://${req.hostname}:${restPort}"
  }
</script>
`;
  res.status(200).send(indexHtml + script);
});

app.listen(port, () => {
  console.log(`Lab UI server listening at http://localhost:${port}`);
});
