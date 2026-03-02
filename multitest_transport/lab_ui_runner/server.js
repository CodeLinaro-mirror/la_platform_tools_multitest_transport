const express = require('express');
const path = require('path');
const fs = require('fs');
const app = express();
const port = process.env.LAB_CONSOLE_PORT || 4200;
const isDevMode = process.env.MTT_CLI_VERSION === 'dev';

console.info('MTT_CLI_VERSION: ', process.env.MTT_CLI_VERSION);

const indexHtmlPath = path.join(__dirname, 'public', 'index.html');
let indexHtml = '';
if (!isDevMode) {
  try {
    indexHtml = fs.readFileSync(indexHtmlPath, 'utf8');
  } catch (err) {
    console.error('Could not read index.html!', err);
    process.exit(1);
  }
}

app.use(express.static(path.join(__dirname, 'public')));


app.get('/*', function(req, res) {
  // we are NOT change the domain/host there, but just append the /labapi
  // path to the url, so that it will be proxy to the ${restPort} by the
  // main server.

  // for performance issue, we read the index.html file content ahead
  // of time, and won't re-read it from the file system every time when a
  // request comes in. But in dev mdoe, we should re-read it every time, as we
  // mihgt need to update the index.html file content.

  let content = indexHtml;
  if (isDevMode) {
    try {
      content = fs.readFileSync(indexHtmlPath, 'utf8');
    } catch (err) {
      console.error('Could not read index.html in dev mode!', err);
      res.status(500).send('Could not read index.html!');
      return;
    }
  }

  // append the init data
  const script = `
<script type="application/json" id="app-data">
  {
    "overrideLabConsoleServerUrl": "/labapi"
  }
</script>
`;
  res.status(200).send(content + script);
});

app.listen(port, () => {
  console.log(`Lab UI server listening at http://localhost:${port}`);
});
