# Visual language

A short record of the decisions the interface is built on. Not a style guide
in general — a description of what is already there, so that changes do not
drift away from it.

## Principles

**One accent colour for the whole system.** Blue `#0066cc` (`#2997ff` on dark)
means "this can be pressed" and nothing else. There is no second accent.

The one exception is red on irreversible actions: shutdown, restart,
hibernate, sign-out. The specification this language comes from describes
showcase pages where nothing can be broken; here something can, and warning by
colour matters more than literal purity. iOS does exactly the same.

**Shape carries meaning.** A pill is an action. An 18px radius is a card. 8 and
11 are utility details. There is nothing in between.

**No shadows on the interface.** Not on cards, not on buttons, not on text.
Depth comes from a change of surface and a hairline border at 8% black. The
only blur is behind the save bar, and it is functional: it shows that content
continues underneath.

**The weight ladder is 300 / 400 / 600 / 700.** There is no 500. Body text is
always 400, emphasis inside a line is 600, headings are 600.

**Body text is 17px**, line height 1.47, tracking −0.374. Not 16: the extra
pixel sets the reading pace, and negative tracking at display sizes gives
headings their recognisable density.

## Motion

**Press is `scale(0.95)`.** The same on every button, tile, chip and segment.
It is the only system-wide micro-interaction.

**Hover changes colour only** and lives inside `@media (hover: hover)`. On a
phone a hover state sticks after a tap and reads as a bug, so it is simply
absent there.

**Nothing lifts.** A card that jumps under the cursor distracts and says
nothing.

**Focus is a 2px ring** in `#0071e3` rather than a soft glow: it stays visible
on any surface.

All motion is disabled when the system asks for reduced motion.

## Layout

A phone gets one column. From 900px the status moves to a sticky left column
and the actions take the space that frees up: the grid opens to three columns,
and to four from 1240px.

The settings page uses a sidebar on wide screens and collapses it into a
horizontal strip of tabs on narrow ones. One long list of settings is
unreadable on a monitor: reaching the right section means scrolling past six
others.

The minimum touch target is 44px; primary buttons are 50.

## Themes

Light and dark. They follow the system by default and switch from a button in
the header. Dark values are declared twice — once for the system setting and
once for an explicit choice — because CSS cannot reference another block, and
copying thirteen variables is cheaper than a JavaScript shim.

The choice is applied before the page paints: otherwise a dark theme would
flash white first.

## Type

System stack: `-apple-system, BlinkMacSystemFont, system-ui`. On a phone that
resolves to the real SF Pro, and the phone is the primary client here. No web
fonts are loaded on purpose — the remote has to open without internet access.

## Tokens

Every value is a variable in `:root` in
[app/static/style.css](../app/static/style.css). There are no inline colours or
radii in the code: if a value is needed, it goes into the tokens.
