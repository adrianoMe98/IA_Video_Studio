/* Slide Studio: desenha as mesmas formas/textos do preview SVG como objetos PPTX editáveis. */
'use strict';
const fs = require('node:fs');
const pptxgen = require('pptxgenjs');
if(process.argv.length!==4){throw new Error('Uso: node export_pptx.cjs slides.json slides.pptx')}
const slides = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const pptx = new pptxgen();
pptx.defineLayout({name:'CUSTOM_16_9', width:13.333333, height:7.5});
pptx.layout='CUSTOM_16_9';
pptx.author='IA Video Studio';pptx.subject='Slides editáveis gerados pelo Slide Studio';pptx.lang='pt-BR';
const X=(n)=>n/96;
const color=(c)=>(c||'#FFFFFF').replace(/^#/,'');
for(const plan of slides){
  const slide=pptx.addSlide();slide.background={color:'FFFFFF'};
  for(const e of plan.elements){
    if(e.type==='rect'){
      const opt={x:X(e.x),y:X(e.y),w:X(e.w),h:X(e.h),rectRadius:X(e.radius||0),
        line:e.stroke?{color:color(e.stroke),width:Math.max(.2,e.sw*.75)}:{color:color(e.fill),transparency:100},
        fill:{color:color(e.fill)}};
      slide.addShape(e.radius?pptx.ShapeType.roundRect:pptx.ShapeType.rect,opt);
    } else if(e.type==='ellipse'){
      slide.addShape(pptx.ShapeType.ellipse,{x:X(e.x),y:X(e.y),w:X(e.w),h:X(e.h),
        line:{color:color(e.fill),transparency:100},fill:{color:color(e.fill)}});
    } else if(e.type==='line'){
      slide.addShape(pptx.ShapeType.line,{x:X(e.x),y:X(e.y),w:X(e.x2-e.x),h:X(e.y2-e.y),
        line:{color:color(e.stroke),width:Math.max(0.5,e.sw*.75)}});
    } else if(e.type==='text'){
      slide.addText(e.lines.join('\n'),{x:X(e.x),y:X(e.y+3),w:X(e.w),h:X(e.h),
        fontFace:'DejaVu Sans',fontSize:e.fontSize*.75,bold:Boolean(e.bold),color:color(e.color),
        breakLine:false,margin:0,valign:'top',align:e.align||'left',
        lineSpacingMultiple:1,fit:'shrink',transparency:0});
    } else if(e.type==='image'){
      slide.addImage({data:e.data,x:X(e.x),y:X(e.y),w:X(e.w),h:X(e.h),sizingCrop:false});
    }
  }
}
pptx.writeFile({fileName:process.argv[3]})
 .then(()=>process.stdout.write(`Created ${slides.length} slides\n`))
 .catch(e=>{console.error(e);process.exit(1)});
