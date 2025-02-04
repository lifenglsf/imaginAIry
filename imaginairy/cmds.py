import logging.config

import click

from imaginairy import LazyLoadingImage, generate_caption
from imaginairy.api import imagine_image_files, load_model
from imaginairy.samplers.base import SAMPLER_TYPE_OPTIONS
from imaginairy.schema import ImaginePrompt
from imaginairy.suppress_logs import suppress_annoying_logs_and_warnings

logger = logging.getLogger(__name__)


def configure_logging(level="INFO"):
    fmt = "%(message)s"
    if level == "DEBUG":
        fmt = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "standard": {"format": fmt},
        },
        "handlers": {
            "default": {
                "level": "INFO",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",  # Default is stderr
            },
        },
        "loggers": {
            "": {  # root logger
                "handlers": ["default"],
                "level": "WARNING",
                "propagate": False,
            },
            "imaginairy": {"handlers": ["default"], "level": level, "propagate": False},
            "transformers.modeling_utils": {
                "handlers": ["default"],
                "level": "ERROR",
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(LOGGING_CONFIG)


@click.command()
@click.argument("prompt_texts", nargs=-1)
@click.option(
    "--prompt-strength",
    default=7.5,
    show_default=True,
    help="How closely to follow the prompt. Image looks unnatural at higher values",
)
@click.option(
    "--init-image",
    help="Starting image. filepath or url",
)
@click.option(
    "--init-image-strength",
    default=0.6,
    show_default=True,
    help="Starting image.",
)
@click.option("--outdir", default="./outputs", help="where to write results to")
@click.option(
    "-r",
    "--repeats",
    default=1,
    type=int,
    help="How many times to repeat the renders. If you provide two prompts and --repeat=3 then six images will be generated",
)
@click.option(
    "-h",
    "--height",
    default=512,
    type=int,
    help="image height. should be multiple of 64",
)
@click.option(
    "-w", "--width", default=512, type=int, help="image width. should be multiple of 64"
)
@click.option(
    "--steps",
    default=40,
    type=int,
    show_default=True,
    help="How many diffusion steps to run. More steps, more detail, but with diminishing returns",
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help="What seed to use for randomness. Allows reproducible image renders",
)
@click.option("--upscale", is_flag=True)
@click.option("--fix-faces", is_flag=True)
@click.option(
    "--sampler-type",
    default="plms",
    type=click.Choice(SAMPLER_TYPE_OPTIONS),
    help="What sampling strategy to use",
)
@click.option("--ddim-eta", default=0.0, type=float)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="What level of logs to show.",
)
@click.option(
    "--show-work",
    default=["none"],
    type=click.Choice(["none", "images", "video"]),
    multiple=True,
    help="Make a video showing the image being created",
)
@click.option(
    "--tile",
    is_flag=True,
    help="Any images rendered will be tileable.  Unfortunately cannot be controlled at the per-image level yet",
)
@click.option(
    "--mask-image",
    help="A mask to use for inpainting. White gets painted, Black is left alone.",
)
@click.option(
    "--mask-prompt",
    help="Describe what you want masked and the AI will mask it for you",
)
@click.option(
    "--mask-mode",
    default="replace",
    type=click.Choice(["keep", "replace"]),
    help="Should we replace the masked area or keep it?",
)
@click.option(
    "--mask-expansion",
    default="2",
    type=int,
    help="How much to grow (or shrink) the mask area",
)
@click.option(
    "--caption",
    default=False,
    is_flag=True,
    help="Generate a text description of the generated image",
)
@click.pass_context
def imagine_cmd(
    ctx,
    prompt_texts,
    prompt_strength,
    init_image,
    init_image_strength,
    outdir,
    repeats,
    height,
    width,
    steps,
    seed,
    upscale,
    fix_faces,
    sampler_type,
    ddim_eta,
    log_level,
    show_work,
    tile,
    mask_image,
    mask_prompt,
    mask_mode,
    mask_expansion,
    caption,
):
    """Have the AI generate images. alias:imagine"""
    if ctx.invoked_subcommand is not None:
        return
    suppress_annoying_logs_and_warnings()
    configure_logging(log_level)

    total_image_count = len(prompt_texts) * repeats
    logger.info(
        f"🤖🧠 imaginAIry received {len(prompt_texts)} prompt(s) and will repeat them {repeats} times to create {total_image_count} images."
    )
    if init_image and sampler_type != "ddim":
        sampler_type = "ddim"
        logger.info("   Sampler type switched to ddim for img2img")

    if init_image and init_image.startswith("http"):
        init_image = LazyLoadingImage(url=init_image)

    prompts = []
    load_model(tile_mode=tile)
    for _ in range(repeats):
        for prompt_text in prompt_texts:
            prompt = ImaginePrompt(
                prompt_text,
                prompt_strength=prompt_strength,
                init_image=init_image,
                init_image_strength=init_image_strength,
                seed=seed,
                sampler_type=sampler_type,
                steps=steps,
                height=height,
                width=width,
                mask_image=mask_image,
                mask_prompt=mask_prompt,
                mask_expansion=mask_expansion,
                mask_mode=mask_mode,
                upscale=upscale,
                fix_faces=fix_faces,
            )
            prompts.append(prompt)

    imagine_image_files(
        prompts,
        outdir=outdir,
        ddim_eta=ddim_eta,
        record_step_images="images" in show_work,
        tile_mode=tile,
        output_file_extension="png",
        print_caption=caption,
    )


@click.group("aimg")
def aimg():
    pass


@click.argument("image_filepaths", nargs=-1)
@aimg.command()
def describe(image_filepaths):
    """Generate text descriptions of images"""
    imgs = []
    for p in image_filepaths:
        if p.startswith("http"):
            img = LazyLoadingImage(url=p)
        else:
            img = LazyLoadingImage(filepath=p)
        imgs.append(img)
    for img in imgs:
        print(generate_caption(img.copy()))


aimg.add_command(imagine_cmd, name="generate")

if __name__ == "__main__":
    imagine_cmd()  # noqa
