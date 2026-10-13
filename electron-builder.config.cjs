module.exports = {
  appId: 'studio.illuminati.comicmetadata', productName: 'Comic Metadata', asar: true,
  directories: { output: 'dist', buildResources: 'desktop/assets' },
  files: ['desktop/**/*', 'package.json', '!desktop/**/*.map'],
  extraResources: [
    { from: 'build/staged/engine', to: 'engine', filter: ['**/*'] },
    { from: 'build/staged/runtime', to: 'runtime', filter: ['**/*'] },
    { from: 'build/staged/licenses', to: 'licenses', filter: ['**/*'] },
  ],
  beforePack: require('./scripts/packaging/verify-staged.cjs'),
  win: { target: [{ target: 'nsis', arch: ['x64'] }], icon: 'desktop/assets/icon.ico', artifactName: 'Comic-Metadata-Setup-${version}-${arch}.${ext}' },
  nsis: { oneClick: true, perMachine: false, allowElevation: false, deleteAppDataOnUninstall: false, createDesktopShortcut: true, createStartMenuShortcut: true, shortcutName: 'Comic Metadata', runAfterFinish: true },
  publish: [{ provider: 'github', owner: 'Gemanoneko', repo: 'Comics_Meta', releaseType: 'release' }],
};
